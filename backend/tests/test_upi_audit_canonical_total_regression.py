"""Paid reconciliation validates failed history against the order's canonical total.

A stale or corrupted attempt amount is itself a mismatch, but must not be
used as the payment-history reference amount or crash the read-only audit.
Disposable database fixture and mocked provider history only.
"""
from decimal import Decimal

from sqlalchemy import select

from app.models.integrations import PaymentAttempt
from app.scripts import audit_upi_payments
from tests.factories import make_order, session


def test_paid_audit_uses_order_total_for_failed_history(monkeypatch):
    with session() as db:
        order = make_order(db)
        attempt = db.scalar(select(PaymentAttempt).where(PaymentAttempt.order_id == order.id))
        attempt.amount = order.total + Decimal("1.00")
        db.commit()
        number = order.order_number
        provider_order_id = attempt.provider_order_id
        provider_payment_id = attempt.provider_payment_id
        canonical_total = order.total

        calls = []
        original = audit_upi_payments.amount_to_subunits

        def checked_conversion(amount):
            calls.append(amount)
            assert amount == canonical_total
            return original(amount)

        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(audit_upi_payments, "amount_to_subunits", checked_conversion)
        monkeypatch.setattr(
            audit_upi_payments,
            "list_razorpay_order_payments",
            lambda **_: [
                {"id": provider_payment_id, "order_id": provider_order_id,
                 "status": "captured", "amount": original(canonical_total),
                 "currency": "INR"},
                {"id": "pay_failed_other", "order_id": provider_order_id,
                 "status": "failed", "amount": original(canonical_total),
                 "currency": "INR"},
            ],
        )

        report = audit_upi_payments.audit_paid_upi()
        finding = next(row for row in report["findings"] if row["order_number"] == number)
        assert finding["result"] == "capture_mismatch"
        assert report["requires_review"] >= 1
        assert calls and all(amount == canonical_total for amount in calls)
