"""Read-only UPI audit must surface every ambiguous captured payment."""
from uuid import uuid4

from sqlalchemy import select

from app.models.integrations import PaymentAttempt
from app.scripts import audit_upi_payments
from app.services.payments import PaymentProviderUnavailable
from tests.factories import make_order, session


def _capture(attempt, payment_id):
    return {
        "id": payment_id, "order_id": attempt.provider_order_id,
        "status": "captured", "amount": 12000, "currency": "INR",
    }


def test_audit_reports_multiple_captures_even_when_one_matches(monkeypatch):
    with session() as db:
        order = make_order(db)
        attempt = db.scalar(
            select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
        )
        db.commit()
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments",
            lambda **_: [
                _capture(attempt, attempt.provider_payment_id),
                _capture(attempt, f"pay_{uuid4().hex}"),
            ],
        )
        report = audit_upi_payments.audit_paid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == order.order_number)
        assert finding["result"] == "multiple_captures"


def test_audit_does_not_hide_unavailable_attempt_behind_verified_capture(monkeypatch):
    with session() as db:
        order = make_order(db)
        first = db.scalar(
            select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
        )
        second = PaymentAttempt(
            order_id=order.id, provider="razorpay",
            provider_order_id=f"order_{uuid4().hex}",
            status="attempted", amount=order.total, currency="INR",
        )
        db.add(second)
        db.commit()
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)

        def history(*, provider_order_id):
            if provider_order_id == first.provider_order_id:
                return [_capture(first, first.provider_payment_id)]
            raise PaymentProviderUnavailable("Simulated outage")

        monkeypatch.setattr(audit_upi_payments, "list_razorpay_order_payments", history)
        report = audit_upi_payments.audit_paid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == order.order_number)
        assert finding["result"] == "provider_unavailable"
