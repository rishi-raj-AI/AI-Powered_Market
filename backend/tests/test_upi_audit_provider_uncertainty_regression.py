"""A valid capture must not mask a provider read failure or contradictory history.

All cases use disposable fixtures and mocked provider reads; no payment I/O.
"""
import pytest
from sqlalchemy import select

from app.models.integrations import PaymentAttempt
from app.scripts import audit_upi_payments
from app.services.payments import PaymentProviderError, PaymentProviderUnavailable
from tests.factories import make_order, session


@pytest.mark.parametrize("error_type", [PaymentProviderError, PaymentProviderUnavailable])
def test_paid_audit_quarantines_provider_read_failure(monkeypatch, error_type):
    with session() as db:
        order = make_order(db)
        db.commit()
        number = order.order_number
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)

        def fail_provider_read(**kwargs):
            raise error_type("mock provider failure")

        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments", fail_provider_read
        )
        report = audit_upi_payments.audit_paid_upi()
        finding = next(row for row in report["findings"] if row["order_number"] == number)
        assert finding["result"] == "provider_unavailable"
        assert report["verified"] == 0
        assert report["requires_review"] >= 1


@pytest.mark.parametrize("secondary_status", ["authorized", "created", "processing", "refunded"])
@pytest.mark.parametrize("history_order", ["before", "after"])
def test_paid_audit_quarantines_unsettled_history_regardless_of_order(
    monkeypatch, secondary_status, history_order
):
    with session() as db:
        order = make_order(db)
        attempt = db.scalar(select(PaymentAttempt).where(PaymentAttempt.order_id == order.id))
        db.commit()
        number = order.order_number
        capture = {
            "id": attempt.provider_payment_id,
            "order_id": attempt.provider_order_id,
            "status": "captured",
            "amount": 12000,
            "currency": "INR",
        }
        unsettled = {
            "id": "pay_unsettled_secondary",
            "order_id": attempt.provider_order_id,
            "status": secondary_status,
            "amount": 12000,
            "currency": "INR",
        }
        history = [unsettled, capture] if history_order == "before" else [capture, unsettled]
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments", lambda **_: history
        )
        report = audit_upi_payments.audit_paid_upi()
        finding = next(row for row in report["findings"] if row["order_number"] == number)
        assert finding["result"] == "provider_ambiguous"
        assert report["verified"] == 0
        assert report["requires_review"] >= 1
