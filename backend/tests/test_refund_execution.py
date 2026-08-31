"""P0-A: a cancelled paid order must actually return the customer's money.

Before this change the backend wrote ``payment_status = refunded`` and made no
provider call at all. These tests pin the properties that make that impossible
to reintroduce.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.integrations import PaymentRefund
from app.models.orders import OrderStatus, PaymentMethod, PaymentStatus
from app.services import refunds as refund_service
from app.services.refunds import (
    REFUND_FAILED,
    REFUND_PROCESSING,
    REFUND_REASON_CANCELLED,
    REFUND_SUCCEEDED,
    dispatch_due_refunds,
    dispatch_refund,
    ensure_refund_request,
    get_refund_for_order,
)
from tests.factories import make_order, session


def _rid(label: str) -> str:
    """Provider ids are globally unique; the test database persists between runs."""
    return f"{label}_{uuid4().hex[:12]}"


class _ProviderSpy:
    def __init__(self, result=None, error=None):
        self.calls: list[dict] = []
        self._result = result
        self._error = error

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._result


def _enable_provider(monkeypatch) -> None:
    monkeypatch.setattr(refund_service, "razorpay_enabled", lambda: True)


def test_cancelling_paid_upi_order_records_refund_and_never_claims_refunded() -> None:
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()

        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()

        assert refund is not None
        assert refund.status == "requested"
        assert refund.amount == order.total
        assert refund.reason == REFUND_REASON_CANCELLED
        # The customer is owed money; nothing may claim it has been returned.
        assert order.payment_status == PaymentStatus.REFUND_PENDING


def test_duplicate_cancellation_does_not_create_a_second_refund() -> None:
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()

        first = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        second = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()

        assert first is not None and second is not None
        assert first.id == second.id
        count = (
            db.query(PaymentRefund).filter(PaymentRefund.order_id == order.id).count()
        )
        assert count == 1


def test_cod_order_never_creates_a_provider_refund() -> None:
    with session() as db:
        order = make_order(
            db,
            payment_method=PaymentMethod.COD,
            payment_status=PaymentStatus.PAID,
            with_paid_attempt=False,
        )
        db.commit()

        assert ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED) is None
        assert get_refund_for_order(db, order.id) is None
        assert order.payment_status == PaymentStatus.PAID


def test_cancellation_before_payment_owes_nothing() -> None:
    with session() as db:
        order = make_order(
            db,
            payment_status=PaymentStatus.PENDING,
            with_paid_attempt=False,
        )
        db.commit()

        assert ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED) is None
        assert get_refund_for_order(db, order.id) is None


def test_successful_provider_refund_marks_order_refunded_once(monkeypatch) -> None:
    _enable_provider(monkeypatch)
    provider_refund_id = _rid("rfnd_success")
    spy = _ProviderSpy(result={"id": provider_refund_id, "status": "processed"})
    monkeypatch.setattr(refund_service, "create_razorpay_refund", spy)

    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        refund_id = refund.id

        assert dispatch_refund(db, refund_id) == REFUND_SUCCEEDED
        assert len(spy.calls) == 1

        # A second dispatch is a no-op: the provider must not be called twice.
        assert dispatch_refund(db, refund_id) == REFUND_SUCCEEDED
        assert len(spy.calls) == 1

        db.refresh(refund)
        db.refresh(order)
        assert refund.provider_refund_id == provider_refund_id
        assert refund.processed_at is not None
        assert order.payment_status == PaymentStatus.REFUNDED


def test_provider_failure_leaves_a_recoverable_obligation(monkeypatch) -> None:
    _enable_provider(monkeypatch)
    boom = _ProviderSpy(error=refund_service.PaymentProviderError("Unable to reach Razorpay"))
    monkeypatch.setattr(refund_service, "create_razorpay_refund", boom)

    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()

        assert dispatch_refund(db, refund.id) == REFUND_FAILED
        db.refresh(refund)
        db.refresh(order)

        assert refund.attempt_count == 1
        assert refund.failure_reason
        assert refund.failed_at is not None
        # Critically: a provider outage must never look like a completed refund.
        assert order.payment_status == PaymentStatus.REFUND_PENDING
        # And the obligation stays visible to the retry worker.
        assert refund.id in refund_service.due_refund_ids(db, order_id=order.id)


def test_failed_refund_is_retried_and_can_succeed(monkeypatch) -> None:
    _enable_provider(monkeypatch)
    boom = _ProviderSpy(error=refund_service.PaymentProviderError("network"))
    monkeypatch.setattr(refund_service, "create_razorpay_refund", boom)

    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        dispatch_refund(db, refund.id)

        ok = _ProviderSpy(result={"id": _rid("rfnd_retry_1"), "status": "processed"})
        monkeypatch.setattr(refund_service, "create_razorpay_refund", ok)
        outcome = dispatch_due_refunds(db, order_id=order.id)

        assert outcome["succeeded"] == 1
        db.refresh(order)
        assert order.payment_status == PaymentStatus.REFUNDED


def test_pending_provider_refund_waits_for_confirmation(monkeypatch) -> None:
    _enable_provider(monkeypatch)
    provider_refund_id = _rid("rfnd_pending")
    spy = _ProviderSpy(result={"id": provider_refund_id, "status": "pending"})
    monkeypatch.setattr(refund_service, "create_razorpay_refund", spy)

    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()

        assert dispatch_refund(db, refund.id) == REFUND_PROCESSING
        db.refresh(order)
        # Provider accepted but has not settled: still not "refunded".
        assert order.payment_status == PaymentStatus.REFUND_PENDING

        # The later webhook is what completes it.
        refund_service.apply_provider_refund_result(
            db, refund, {"id": provider_refund_id, "status": "processed"}
        )
        db.commit()
        db.refresh(order)
        assert order.payment_status == PaymentStatus.REFUNDED


def test_refund_without_captured_payment_id_is_flagged_for_reconciliation(monkeypatch) -> None:
    _enable_provider(monkeypatch)
    spy = _ProviderSpy(result={"id": _rid("rfnd_never"), "status": "processed"})
    monkeypatch.setattr(refund_service, "create_razorpay_refund", spy)

    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID, with_paid_attempt=False)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()

        assert refund is not None and refund.provider_payment_id is None
        assert dispatch_refund(db, refund.id) == REFUND_FAILED
        assert spy.calls == []
        db.refresh(refund)
        assert "manual reconciliation" in (refund.failure_reason or "")


def test_terminal_refunded_order_stays_refunded_on_repeat_webhook(monkeypatch) -> None:
    _enable_provider(monkeypatch)
    provider_refund_id = _rid("rfnd_terminal")
    monkeypatch.setattr(
        refund_service,
        "create_razorpay_refund",
        _ProviderSpy(result={"id": provider_refund_id, "status": "processed"}),
    )

    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        dispatch_refund(db, refund.id)

        for _ in range(3):
            refund_service.apply_provider_refund_result(
                db, refund, {"id": provider_refund_id, "status": "processed"}
            )
            db.commit()

        db.refresh(order)
        assert order.payment_status == PaymentStatus.REFUNDED
        assert (
            db.query(PaymentRefund).filter(PaymentRefund.order_id == order.id).count() == 1
        )


def test_refund_amount_matches_order_total_exactly() -> None:
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID, total=Decimal("437.50"))
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        assert refund is not None
        assert Decimal(refund.amount) == Decimal("437.50")


@pytest.mark.parametrize(
    "order_status",
    [OrderStatus.PLACED, OrderStatus.ACCEPTED, OrderStatus.CANCELLED],
)
def test_refund_obligation_is_independent_of_order_status(order_status) -> None:
    with session() as db:
        order = make_order(db, status=order_status, payment_status=PaymentStatus.PAID)
        db.commit()
        assert ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED) is not None
