"""A matching capture must not certify duplicated local Razorpay order identities.

Read-only audit with disposable fixtures and mocked provider I/O.
"""
import pytest
from sqlalchemy import select

from app.models.integrations import PaymentAttempt
from app.scripts import audit_upi_payments
from tests.factories import make_order, session


@pytest.mark.parametrize("second_status", ["created", "attempted", "failed", "paid"])
def test_paid_audit_quarantines_duplicate_local_provider_order(monkeypatch, second_status):
    with session() as db:
        order = make_order(db)
        original = db.scalar(
            select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
        )
        duplicate = PaymentAttempt(
            order_id=order.id,
            provider="razorpay",
            provider_order_id=original.provider_order_id,
            provider_payment_id=(
                "pay_second_local" if second_status == "paid" else None
            ),
            amount=original.amount,
            currency=original.currency,
            status=second_status,
        )
        db.add(duplicate)
        db.commit()
        order_number = order.order_number
        history = [{
            "id": original.provider_payment_id,
            "order_id": original.provider_order_id,
            "status": "captured",
            "amount": 12000,
            "currency": "INR",
        }]
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments", lambda **_: history
        )
        report = audit_upi_payments.audit_paid_upi()
        finding = next(
            row for row in report["findings"] if row["order_number"] == order_number
        )
        assert finding["result"] == "capture_mismatch"
        assert report["verified"] == 0
        assert report["requires_review"] >= 1
