"""Provider history identities must be unique even beside a valid capture.

Disposable database fixtures and mocked provider responses only.
"""
import pytest
from sqlalchemy import select

from app.models.integrations import PaymentAttempt
from app.scripts import audit_upi_payments
from tests.factories import make_order, session


@pytest.mark.parametrize("duplicate_status", ["captured", "failed", "authorized"])
@pytest.mark.parametrize("duplicate_first", [False, True])
def test_paid_audit_quarantines_duplicate_provider_history_identity(
    monkeypatch, duplicate_status, duplicate_first
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
        duplicate = {**capture, "status": duplicate_status}
        history = [duplicate, capture] if duplicate_first else [capture, duplicate]
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments", lambda **_: history
        )
        report = audit_upi_payments.audit_paid_upi()
        finding = next(row for row in report["findings"] if row["order_number"] == number)
        assert finding["result"] == "capture_mismatch"
        assert report["verified"] == 0
        assert report["requires_review"] >= 1
