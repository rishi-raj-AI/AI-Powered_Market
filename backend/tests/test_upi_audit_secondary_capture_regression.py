"""Paid UPI reconciliation must not certify a capture beside unresolved evidence.

Disposable order fixtures and mocked provider reads only; no real payment I/O.
"""
import pytest
from sqlalchemy import select

from app.models.integrations import PaymentAttempt
from app.scripts import audit_upi_payments
from tests.factories import make_order, session


@pytest.mark.parametrize(
    ("secondary_status", "expected"),
    [
        ("created", "provider_ambiguous"),
        ("authorized", "provider_ambiguous"),
        ("refunded", "provider_ambiguous"),
        ("processing", "provider_ambiguous"),
        ("unexpected", "provider_ambiguous"),
    ],
)
def test_paid_audit_does_not_clear_unsettled_secondary_payment(
    monkeypatch, secondary_status, expected
):
    with session() as db:
        order = make_order(db)
        attempt = db.scalar(
            select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
        )
        db.commit()
        number = order.order_number
        captured = {
            "id": attempt.provider_payment_id,
            "order_id": attempt.provider_order_id,
            "status": "captured",
            "amount": 12000,
            "currency": "INR",
        }
        secondary = {
            "id": "pay_unsettled_other",
            "order_id": attempt.provider_order_id,
            "status": secondary_status,
            "amount": 12000,
            "currency": "INR",
        }
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments,
            "list_razorpay_order_payments",
            lambda **_: [captured, secondary],
        )

        report = audit_upi_payments.audit_paid_upi()
        finding = next(
            row for row in report["findings"] if row["order_number"] == number
        )
        assert finding["result"] == expected
        assert report["requires_review"] >= 1
        assert report["verified"] == 0


@pytest.mark.parametrize(
    "malformed",
    [
        {"id": None},
        {"id": ""},
        {"id": "pay_other", "order_id": "order_wrong"},
        {"id": "pay_other", "amount": True},
        {"id": "pay_other", "currency": "USD"},
    ],
)
def test_paid_audit_rejects_malformed_secondary_capture(monkeypatch, malformed):
    with session() as db:
        order = make_order(db)
        attempt = db.scalar(
            select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
        )
        db.commit()
        number = order.order_number
        captured = {
            "id": attempt.provider_payment_id,
            "order_id": attempt.provider_order_id,
            "status": "captured",
            "amount": 12000,
            "currency": "INR",
        }
        secondary = {
            "id": "pay_other",
            "order_id": attempt.provider_order_id,
            "status": "captured",
            "amount": 12000,
            "currency": "INR",
        }
        secondary.update(malformed)
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments,
            "list_razorpay_order_payments",
            lambda **_: [captured, secondary],
        )

        report = audit_upi_payments.audit_paid_upi()
        finding = next(
            row for row in report["findings"] if row["order_number"] == number
        )
        assert finding["result"] != "verified_capture"
        assert report["requires_review"] >= 1
