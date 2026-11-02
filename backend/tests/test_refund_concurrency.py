"""PostgreSQL acceptance for refund webhook/dispatcher concurrency.

These tests use disposable test orders and mocked Razorpay I/O only.
They deliberately exercise distinct SQLAlchemy sessions and real row locks.
"""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event, Lock
from uuid import uuid4

from app.api.v1.routes.payment_hardening import _process_refund_event
from app.models.integrations import PaymentRefund
from app.models.orders import Order, PaymentStatus
from app.services import refunds
from app.services.payments import PaymentProviderIndeterminate, amount_to_subunits
from app.services.refunds import REFUND_REASON_CANCELLED, ensure_refund_request
from tests.factories import make_order, session


def _refund_context():
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        assert refund is not None and refund.provider_payment_id
        db.commit()
        return order.id, refund.id, refund.provider_payment_id, Decimal(refund.amount)


def _processed_payload(payment_id, amount, refund_id):
    return {
        "event": "refund.processed",
        "payload": {"refund": {"entity": {
            "id": refund_id,
            "payment_id": payment_id,
            "amount": amount_to_subunits(amount),
            "currency": "INR",
            "status": "processed",
        }}},
    }


def test_duplicate_refund_webhooks_serialize_on_order_lock(monkeypatch):
    """A second webhook waits for the first transaction and cannot settle twice."""
    order_id, refund_id, payment_id, amount = _refund_context()
    provider_refund_id = f"rfnd_concurrent_{uuid4().hex}"
    payload = _processed_payload(payment_id, amount, provider_refund_id)
    first_processed = Event()
    release_first = Event()
    second_started = Event()
    second_finished = Event()
    settlements = []
    settlement_lock = Lock()

    def record_settlement(_db, order):
        with settlement_lock:
            settlements.append(order.id)

    monkeypatch.setattr(refunds, "settle_refunded_order", record_settlement)

    def first():
        with session() as db:
            result = _process_refund_event(db, payload)
            assert result is True
            first_processed.set()
            assert release_first.wait(timeout=15), "Timed out holding refund order lock"
            db.commit()
            return result

    def second():
        with session() as db:
            second_started.set()
            try:
                result = _process_refund_event(db, payload)
                db.commit()
                return result
            finally:
                second_finished.set()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(first)
            assert first_processed.wait(timeout=15), "First webhook did not acquire order lock"
            second_future = executor.submit(second)
            assert second_started.wait(timeout=15)
            assert not second_finished.wait(timeout=0.25), (
                "Competing webhook completed while first transaction held order lock"
            )
            release_first.set()
            assert first_future.result(timeout=15) is True
            assert second_future.result(timeout=15) is True
    finally:
        release_first.set()

    assert settlements == [order_id]
    with session() as db:
        order = db.get(Order, order_id)
        refund = db.get(PaymentRefund, refund_id)
        assert order.payment_status == PaymentStatus.REFUNDED
        assert refund.status == refunds.REFUND_SUCCEEDED
        assert refund.provider_refund_id == provider_refund_id


def test_refund_webhook_success_survives_inflight_dispatch_timeout(monkeypatch):
    """Provider timeout after webhook success must not resubmit or downgrade refund."""
    order_id, refund_id, payment_id, amount = _refund_context()
    provider_refund_id = f"rfnd_race_{uuid4().hex}"
    provider_entered = Event()
    release_provider = Event()
    provider_calls = []
    settlements = []

    def mock_provider(*, provider_payment_id, amount, idempotency_key, notes):
        provider_calls.append((provider_payment_id, idempotency_key))
        provider_entered.set()
        assert release_provider.wait(timeout=15), "Timed out waiting for refund webhook"
        raise PaymentProviderIndeterminate("Simulated provider timeout after refund acceptance")

    monkeypatch.setattr(refunds, "razorpay_enabled", lambda: True)
    monkeypatch.setattr(refunds, "create_razorpay_refund", mock_provider)
    monkeypatch.setattr(
        refunds, "settle_refunded_order",
        lambda _db, order: settlements.append(order.id),
    )

    def dispatch():
        with session() as db:
            return refunds.dispatch_refund(db, refund_id)

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            dispatch_future = executor.submit(dispatch)
            assert provider_entered.wait(timeout=15), "Dispatcher never reached mocked provider"
            with session() as db:
                assert _process_refund_event(
                    db, _processed_payload(payment_id, amount, provider_refund_id),
                ) is True
                db.commit()
            release_provider.set()
            assert dispatch_future.result(timeout=15) == refunds.REFUND_SUCCEEDED
    finally:
        release_provider.set()

    assert len(provider_calls) == 1
    assert provider_calls[0][0] == payment_id
    assert settlements == [order_id]
    with session() as db:
        order = db.get(Order, order_id)
        refund = db.get(PaymentRefund, refund_id)
        assert order.payment_status == PaymentStatus.REFUNDED
        assert refund.status == refunds.REFUND_SUCCEEDED
        assert refund.provider_refund_id == provider_refund_id
        assert refund.attempt_count == 1
