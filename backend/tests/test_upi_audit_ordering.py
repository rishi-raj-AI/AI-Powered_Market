"""Stable, bounded read-only reconciliation when orders share a timestamp."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.integrations import PaymentAttempt
from app.models.orders import PaymentStatus
from app.scripts import audit_upi_payments
from tests.factories import make_order, session


@pytest.mark.parametrize("unpaid", [False, True])
def test_limited_upi_audit_orders_equal_timestamps_by_descending_id(monkeypatch, unpaid):
    # A limit must choose the same order across repeated staging audits;
    # the extra row must still be counted as truncated coverage.
    with session() as db:
        status = PaymentStatus.PENDING if unpaid else PaymentStatus.PAID
        first = make_order(db, payment_status=status, with_paid_attempt=not unpaid)
        second = make_order(db, payment_status=status, with_paid_attempt=not unpaid)
        shared_timestamp = datetime.now(timezone.utc)
        first.created_at = shared_timestamp
        second.created_at = shared_timestamp
        db.flush()
        expected = max((first, second), key=lambda order: order.id).order_number
        db.commit()
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)

        def provider_history(*, provider_order_id):
            attempt = db.scalar(select(PaymentAttempt).where(
                PaymentAttempt.provider_order_id == provider_order_id
            ))
            return [{
                "id": attempt.provider_payment_id,
                "order_id": provider_order_id,
                "status": "captured",
                "amount": 12000,
                "currency": "INR",
            }]

        if not unpaid:
            monkeypatch.setattr(
                audit_upi_payments, "list_razorpay_order_payments", provider_history
            )
        audit = (
            audit_upi_payments.audit_unpaid_upi if unpaid
            else audit_upi_payments.audit_paid_upi
        )
        first_report = audit(limit=1)
        second_report = audit(limit=1)
        assert first_report == second_report
        assert first_report["scanned"] == 1
        assert first_report["truncated"] is True
        assert first_report["findings"][0]["order_number"] == expected
