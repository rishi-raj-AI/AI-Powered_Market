"""Real PostgreSQL row-lock acceptance for duplicate Razorpay capture delivery.

The tests use disposable factory orders and mocked provider responses. They do
not contact Razorpay, issue refunds, or access production financial records.
"""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Event, Lock
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from starlette.requests import Request

from app.api.v1.routes import payment_hardening
from app.models.integrations import PaymentAttempt, PaymentWebhookEvent
from app.models.orders import PaymentStatus
from app.services.payment_webhook_replay import replay_pending_payment_webhooks
from tests.factories import make_order, make_user, session


def _duplicate_request(body: bytes, event_key: str) -> Request:
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/payments/webhook",
            "headers": [
                (b"x-razorpay-signature", b"mock-signature"),
                (b"x-razorpay-event-id", event_key.encode("ascii")),
            ],
        },
        receive,
    )


@pytest.mark.parametrize("competing_delivery", ["replay_worker", "duplicate_webhook"])
def test_capture_replay_and_competing_delivery_settle_once(
    monkeypatch, competing_delivery,
):
    """A competing worker or duplicate delivery cannot process a locked event.

    The first worker is held inside the mocked provider read *after* acquiring
    the webhook row lock. A second PostgreSQL session must skip the locked
    event rather than confirm payment or emit a second merchant notification.
    """
    event_key = f"evt_concurrent_{uuid4().hex}"
    payment_id = f"pay_concurrent_{uuid4().hex}"
    provider_order_id = f"order_concurrent_{uuid4().hex}"
    payload = {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {
            "id": payment_id, "order_id": provider_order_id,
        }}},
    }
    with session() as db:
        customer = make_user(db)
        order = make_order(
            db, customer=customer, payment_status=PaymentStatus.PENDING,
            with_paid_attempt=False,
        )
        attempt = PaymentAttempt(
            order_id=order.id,
            provider="razorpay",
            provider_order_id=provider_order_id,
            status="attempted",
            amount=Decimal("120.00"),
            currency="INR",
        )
        db.add(attempt)
        event = PaymentWebhookEvent(
            provider="razorpay",
            event_key=event_key,
            event_type="payment.captured",
            payload=payload,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=2),
        )
        db.add(event)
        db.commit()
        order_id = order.id

    provider_entered = Event()
    release_provider = Event()
    provider_calls = []
    call_lock = Lock()
    settlements = []
    notifications = []

    def verified_capture(*, provider_payment_id):
        with call_lock:
            provider_calls.append(provider_payment_id)
        provider_entered.set()
        assert release_provider.wait(timeout=15), "Timed out waiting for competing delivery"
        return {
            "id": provider_payment_id,
            "order_id": provider_order_id,
            "amount": 12000,
            "currency": "INR",
            "status": "captured",
        }

    monkeypatch.setattr(payment_hardening, "fetch_razorpay_payment", verified_capture)
    monkeypatch.setattr(
        payment_hardening, "verify_razorpay_webhook_signature", lambda **_: True,
    )
    monkeypatch.setattr(
        payment_hardening, "ensure_settlement_entry",
        lambda _db, _order: settlements.append(_order.id),
    )
    monkeypatch.setattr(
        payment_hardening, "_notify_payment_captured",
        lambda _db, _order: notifications.append(_order.id),
    )

    def worker():
        with session() as db:
            return replay_pending_payment_webhooks(db, min_age_seconds=0)

    def duplicate():
        with session() as db:
            body = json.dumps(payload).encode("utf-8")
            return asyncio.run(
                payment_hardening.hardened_razorpay_webhook(
                    request=_duplicate_request(body, event_key), db=db,
                )
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(worker)
            assert provider_entered.wait(timeout=15), "Replay did not lock and reach provider"
            second = executor.submit(
                worker if competing_delivery == "replay_worker" else duplicate
            )
            try:
                competing_result = second.result(timeout=15)
            finally:
                release_provider.set()
            first_result = first.result(timeout=15)

        assert first_result["processed"] == 1
        if competing_delivery == "replay_worker":
            assert competing_result == {"considered": 1, "processed": 0, "deferred": 0}
        else:
            assert competing_result == {"ok": True}
        assert provider_calls == [payment_id]
        assert settlements == [order_id]
        assert notifications == [order_id]
        with session() as db:
            stored = db.scalar(
                select(PaymentWebhookEvent).where(
                    PaymentWebhookEvent.event_key == event_key,
                )
            )
            assert stored is not None and stored.processed_at is not None
            assert db.get(type(order), order_id).payment_status == PaymentStatus.PAID
    finally:
        release_provider.set()
        with session() as db:
            db.execute(
                delete(PaymentWebhookEvent).where(
                    PaymentWebhookEvent.event_key == event_key,
                )
            )
            db.commit()
