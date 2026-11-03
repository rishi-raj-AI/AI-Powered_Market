"""Provider failed-payment evidence must be complete before a paid UPI audit passes.

These tests use disposable database fixtures and mocked provider history; they
never create payments, issue refunds, or access production credentials.
"""
from sqlalchemy import select
import pytest

from app.models.integrations import PaymentAttempt
from app.scripts import audit_upi_payments
from tests.factories import make_order, session


@pytest.mark.parametrize(
    ("mutation", "value"),
    [
        ("id", None),
        ("order_id", "order_unrelated"),
        ("currency", "USD"),
        ("amount", 11999),
        ("amount", True),
    ],
)
def test_paid_audit_rejects_malformed_failed_history_even_with_matching_capture(
    monkeypatch, mutation, value
):
    with session() as db:
        order = make_order(db)
        attempt = db.scalar(
            select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
        )
        db.commit()
        order_number = order.order_number
        capture = {
            "id": attempt.provider_payment_id,
            "order_id": attempt.provider_order_id,
            "status": "captured",
            "amount": 12000,
            "currency": "INR",
        }
        failed = {
            "id": "pay_failed_other",
            "order_id": attempt.provider_order_id,
            "status": "failed",
            "amount": 12000,
            "currency": "INR",
        }
        failed[mutation] = value
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments,
            "list_razorpay_order_payments",
            lambda **_: [capture, failed],
        )

        report = audit_upi_payments.audit_paid_upi()
        finding = next(
            item for item in report["findings"]
            if item["order_number"] == order_number
        )
        assert finding["result"] == "capture_mismatch"
        assert report["requires_review"] >= 1
