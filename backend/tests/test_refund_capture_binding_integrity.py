"""Refund obligations must not auto-select one of several possible captures.

These cases use disposable test orders and no Razorpay calls or live records.
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.integrations import PaymentAttempt
from app.models.orders import PaymentStatus
from app.services import refunds as refund_service
from app.services.refunds import (
    REFUND_FAILED,
    REFUND_REASON_CANCELLED,
    ensure_refund_request,
    dispatch_refund,
)
from tests.factories import make_order, session


@pytest.mark.parametrize("second_status", ["paid", "failed"])
def test_refund_with_two_capture_evidence_rows_requires_manual_reconciliation(
    monkeypatch, second_status,
):
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.add(PaymentAttempt(
            order_id=order.id,
            provider="razorpay",
            provider_order_id=f"order_{uuid4().hex}",
            provider_payment_id=f"pay_{uuid4().hex}",
            status=second_status,
            amount=order.total,
            currency="INR",
        ))
        db.commit()

        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        assert refund is not None
        assert refund.provider_payment_id is None
        assert refund.payment_attempt_id is None
        assert order.payment_status == PaymentStatus.REFUND_PENDING

        monkeypatch.setattr(
            refund_service, "create_razorpay_refund",
            lambda **_kwargs: pytest.fail("Ambiguous capture must never trigger a refund"),
        )
        assert dispatch_refund(db, refund.id) == REFUND_FAILED
        db.refresh(refund)
        assert refund.provider_payment_id is None
        assert "manual reconciliation" in (refund.failure_reason or "")


@pytest.mark.parametrize("invalid", ["missing_payment_id", "amount", "currency", "provider"])
def test_refund_does_not_bind_unverifiable_single_capture(invalid):
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        attempt = db.scalar(
            select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
        )
        assert attempt is not None
        if invalid == "missing_payment_id":
            attempt.provider_payment_id = None
        elif invalid == "amount":
            attempt.amount = Decimal(order.total) - Decimal("1.00")
        elif invalid == "currency":
            attempt.currency = "USD"
        else:
            attempt.provider = "unknown"
        db.commit()

        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        assert refund is not None
        assert refund.provider_payment_id is None
        assert refund.payment_attempt_id is None
        assert order.payment_status == PaymentStatus.REFUND_PENDING


def test_refund_binds_one_consistent_captured_attempt():
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        attempt = db.scalar(
            select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
        )
        assert attempt is not None and attempt.provider_payment_id
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        assert refund is not None
        assert refund.payment_attempt_id == attempt.id
        assert refund.provider_payment_id == attempt.provider_payment_id
