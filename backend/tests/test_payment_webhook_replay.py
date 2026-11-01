"""Deferred capture events remain durable and can be reconciled by the worker."""
from datetime import datetime, timedelta, timezone

from app.api.v1.routes import payment_hardening
from app.models.integrations import PaymentWebhookEvent
from app.models.orders import PaymentStatus
from app.services.payment_webhook_replay import replay_pending_payment_webhooks
from tests.factories import make_order, make_user, session
from app.models.integrations import PaymentAttempt
from decimal import Decimal
from uuid import uuid4


def test_authorized_capture_is_deferred_then_replayed_once(monkeypatch):
    with session() as db:
        customer = make_user(db)
        order = make_order(
            db, customer=customer, payment_status=PaymentStatus.PENDING,
            with_paid_attempt=False,
        )
        attempt = PaymentAttempt(
            order_id=order.id, provider="razorpay",
            provider_order_id=f"order_{uuid4().hex}",
            status="attempted", amount=Decimal("120.00"), currency="INR",
        )
        db.add(attempt)
        db.flush()
        payment_id = f"pay_{uuid4().hex}"
        event = PaymentWebhookEvent(
            provider="razorpay", event_key=f"evt_{uuid4().hex}",
            event_type="payment.captured",
            payload={
                "event": "payment.captured",
                "payload": {"payment": {"entity": {
                    "id": payment_id, "order_id": attempt.provider_order_id,
                }}},
            },
            created_at=datetime.now(timezone.utc) - timedelta(minutes=2),
        )
        db.add(event)
        db.commit()
        status = {"value": "authorized"}
        monkeypatch.setattr(
            payment_hardening, "fetch_razorpay_payment",
            lambda *, provider_payment_id: {
                "id": provider_payment_id, "order_id": attempt.provider_order_id,
                "amount": 12000, "currency": "INR", "status": status["value"],
            },
        )
        settlements = []
        notifications = []
        monkeypatch.setattr(
            payment_hardening, "ensure_settlement_entry",
            lambda _db, _order: settlements.append(_order.id),
        )
        monkeypatch.setattr(
            payment_hardening, "_notify_payment_captured",
            lambda _db, _order: notifications.append(_order.id),
        )
        first = replay_pending_payment_webhooks(db)
        assert first["deferred"] == 1
        db.refresh(order)
        db.refresh(event)
        assert order.payment_status == PaymentStatus.PENDING
        assert event.processed_at is None

        status["value"] = "captured"
        second = replay_pending_payment_webhooks(db)
        assert second["processed"] == 1
        db.refresh(order)
        db.refresh(event)
        assert order.payment_status == PaymentStatus.PAID
        assert event.processed_at is not None
        third = replay_pending_payment_webhooks(db)
        assert third["considered"] == 0
        assert settlements == [order.id]
        assert notifications == [order.id]
