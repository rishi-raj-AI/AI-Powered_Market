"""Signed Razorpay webhooks must survive provider outages and duplicate deliveries.

No external payment API calls or real financial records are used.
"""
import asyncio
import json
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select
from starlette.requests import Request

from app.api.v1.routes import payment_hardening
from app.models.integrations import PaymentWebhookEvent
from tests.factories import session


def _request(body: bytes, event_key: str) -> Request:
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/payments/webhook",
            "headers": [
                (b"x-razorpay-signature", b"test-signature"),
                (b"x-razorpay-event-id", event_key.encode("ascii")),
            ],
        },
        receive,
    )


def _deliver(db, body: bytes, event_key: str):
    return asyncio.run(
        payment_hardening.hardened_razorpay_webhook(
            request=_request(body, event_key), db=db,
        )
    )


def test_provider_outage_preserves_webhook_and_duplicate_can_recover(monkeypatch):
    event_key = f"evt_durable_{uuid4().hex}"
    body = json.dumps({"event": "payment.captured"}).encode("utf-8")
    monkeypatch.setattr(
        payment_hardening, "verify_razorpay_webhook_signature", lambda **_: True,
    )
    calls = []

    def process(_db, _payload):
        calls.append("attempt")
        if len(calls) == 1:
            raise HTTPException(status_code=503, detail="Provider unavailable")
        return True

    monkeypatch.setattr(payment_hardening, "_process_event", process)
    with session() as db:
        try:
            with pytest.raises(HTTPException) as exc:
                _deliver(db, body, event_key)
            assert exc.value.status_code == 503
            stored = db.scalar(
                select(PaymentWebhookEvent).where(
                    PaymentWebhookEvent.event_key == event_key,
                )
            )
            assert stored is not None
            assert stored.processed_at is None
            assert stored.payload["event"] == "payment.captured"

            assert _deliver(db, body, event_key) == {"ok": True}
            db.refresh(stored)
            assert stored.processed_at is not None
            assert len(calls) == 2
            assert _deliver(db, body, event_key) == {"ok": True}
            assert len(calls) == 2
        finally:
            db.rollback()
            db.execute(delete(PaymentWebhookEvent).where(
                PaymentWebhookEvent.event_key == event_key,
            ))
            db.commit()


def test_deferred_webhook_duplicate_is_reprocessed_without_worker(monkeypatch):
    event_key = f"evt_deferred_{uuid4().hex}"
    body = b'{"event":"payment.captured"}'
    monkeypatch.setattr(
        payment_hardening, "verify_razorpay_webhook_signature", lambda **_: True,
    )
    outcomes = iter([False, True])
    monkeypatch.setattr(
        payment_hardening, "_process_event", lambda *_: next(outcomes),
    )
    with session() as db:
        try:
            assert _deliver(db, body, event_key) == {"ok": True}
            stored = db.scalar(
                select(PaymentWebhookEvent).where(
                    PaymentWebhookEvent.event_key == event_key,
                )
            )
            assert stored is not None and stored.processed_at is None
            assert _deliver(db, body, event_key) == {"ok": True}
            db.refresh(stored)
            assert stored.processed_at is not None
        finally:
            db.rollback()
            db.execute(delete(PaymentWebhookEvent).where(
                PaymentWebhookEvent.event_key == event_key,
            ))
            db.commit()


@pytest.mark.parametrize("processed", [False, True])
def test_signed_webhook_event_id_collision_cannot_discard_distinct_payload(
    monkeypatch, processed,
):
    event_key = f"evt_collision_{uuid4().hex}"
    first_body = json.dumps({"event": "payment.captured", "payload": {"payment": {
        "entity": {"id": "pay_original"},
    }}}).encode("utf-8")
    conflicting_body = json.dumps({"event": "payment.captured", "payload": {"payment": {
        "entity": {"id": "pay_different"},
    }}}).encode("utf-8")
    monkeypatch.setattr(
        payment_hardening, "verify_razorpay_webhook_signature", lambda **_: True,
    )
    calls = []
    monkeypatch.setattr(
        payment_hardening, "_process_event",
        lambda *_: calls.append("processed") or processed,
    )
    with session() as db:
        try:
            assert _deliver(db, first_body, event_key) == {"ok": True}
            with pytest.raises(HTTPException) as exc:
                _deliver(db, conflicting_body, event_key)
            assert exc.value.status_code == 409
            stored = db.scalar(
                select(PaymentWebhookEvent).where(
                    PaymentWebhookEvent.event_key == event_key,
                )
            )
            assert stored is not None
            assert stored.payload["payload"]["payment"]["entity"]["id"] == "pay_original"
            assert (stored.processed_at is not None) is processed
            assert calls == ["processed"]
        finally:
            db.rollback()
            db.execute(delete(PaymentWebhookEvent).where(
                PaymentWebhookEvent.event_key == event_key,
            ))
            db.commit()


def test_webhook_rejects_oversized_event_id_before_database_insert(monkeypatch):
    monkeypatch.setattr(
        payment_hardening, "verify_razorpay_webhook_signature", lambda **_: True,
    )
    with session() as db:
        with pytest.raises(HTTPException) as exc:
            _deliver(db, b'{"event":"payment.captured"}', "e" * 161)
        assert exc.value.status_code == 400
