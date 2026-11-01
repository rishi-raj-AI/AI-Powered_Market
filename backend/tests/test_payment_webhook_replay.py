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
        assert event.attempt_count == 1
        assert event.next_attempt_at is not None

        status["value"] = "captured"
        # Deferred events must wait for their due time rather than being
        # repeatedly polled on every worker tick.
        assert replay_pending_payment_webhooks(db)["considered"] == 0
        event.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
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


def test_deferred_oldest_event_does_not_starve_newer_capture(monkeypatch):
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
        first_id = f"pay_{uuid4().hex}"
        second_id = f"pay_{uuid4().hex}"
        older = PaymentWebhookEvent(
            provider="razorpay", event_key=f"evt_{uuid4().hex}",
            event_type="payment.captured",
            payload={"event": "payment.captured", "payload": {"payment": {"entity": {
                "id": first_id, "order_id": attempt.provider_order_id,
            }}}},
            created_at=datetime.now(timezone.utc) - timedelta(minutes=3),
        )
        newer = PaymentWebhookEvent(
            provider="razorpay", event_key=f"evt_{uuid4().hex}",
            event_type="payment.captured",
            payload={"event": "payment.captured", "payload": {"payment": {"entity": {
                "id": second_id, "order_id": attempt.provider_order_id,
            }}}},
            created_at=datetime.now(timezone.utc) - timedelta(minutes=2),
        )
        db.add_all([older, newer])
        db.commit()
        monkeypatch.setattr(
            payment_hardening, "fetch_razorpay_payment",
            lambda *, provider_payment_id: {
                "id": provider_payment_id, "order_id": attempt.provider_order_id,
                "amount": 12000, "currency": "INR",
                "status": "authorized" if provider_payment_id == first_id else "captured",
            },
        )
        monkeypatch.setattr(payment_hardening, "ensure_settlement_entry", lambda *_: None)
        monkeypatch.setattr(payment_hardening, "_notify_payment_captured", lambda *_: None)
        assert replay_pending_payment_webhooks(db, limit=1)["deferred"] == 1
        db.refresh(older)
        assert older.attempt_count == 1
        assert older.next_attempt_at is not None
        second = replay_pending_payment_webhooks(db, limit=1)
        assert second["processed"] == 1
        db.refresh(newer)
        db.refresh(order)
        assert newer.processed_at is not None
        assert order.payment_status == PaymentStatus.PAID
        assert replay_pending_payment_webhooks(db, limit=1)["considered"] == 0


def test_provider_error_persists_backoff_and_recovers(monkeypatch):
    with session() as db:
        customer = make_user(db)
        order = make_order(db, customer=customer, payment_status=PaymentStatus.PENDING, with_paid_attempt=False)
        attempt = PaymentAttempt(
            order_id=order.id, provider="razorpay",
            provider_order_id=f"order_{uuid4().hex}", status="attempted",
            amount=Decimal("120.00"), currency="INR",
        )
        db.add(attempt)
        db.flush()
        payment_id = f"pay_{uuid4().hex}"
        event = PaymentWebhookEvent(
            provider="razorpay", event_key=f"evt_{uuid4().hex}",
            event_type="payment.captured",
            payload={"event": "payment.captured", "payload": {"payment": {"entity": {
                "id": payment_id, "order_id": attempt.provider_order_id,
            }}}},
            created_at=datetime.now(timezone.utc) - timedelta(minutes=2),
        )
        db.add(event)
        db.commit()

        from app.services.payments import PaymentProviderUnavailable

        def unavailable(**_kwargs):
            raise PaymentProviderUnavailable("simulated provider outage")

        monkeypatch.setattr(payment_hardening, "fetch_razorpay_payment", unavailable)
        assert replay_pending_payment_webhooks(db)["deferred"] == 1
        db.refresh(event)
        assert event.attempt_count == 1
        assert event.processed_at is None
        assert event.next_attempt_at is not None
        assert replay_pending_payment_webhooks(db)["considered"] == 0

        monkeypatch.setattr(
            payment_hardening, "fetch_razorpay_payment",
            lambda *, provider_payment_id: {
                "id": provider_payment_id, "order_id": attempt.provider_order_id,
                "amount": 12000, "currency": "INR", "status": "captured",
            },
        )
        monkeypatch.setattr(payment_hardening, "ensure_settlement_entry", lambda *_: None)
        monkeypatch.setattr(payment_hardening, "_notify_payment_captured", lambda *_: None)
        event.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        assert replay_pending_payment_webhooks(db)["processed"] == 1
        db.refresh(event)
        db.refresh(order)
        assert event.processed_at is not None
        assert order.payment_status == PaymentStatus.PAID
