"""Read-only UPI audit must surface every ambiguous captured payment."""
from decimal import Decimal
from uuid import uuid4

import pytest

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
        order_number = order.order_number
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments",
            lambda **_: [
                _capture(attempt, attempt.provider_payment_id),
                _capture(attempt, f"pay_{uuid4().hex}"),
            ],
        )
        report = audit_upi_payments.audit_paid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == order_number)
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
        order_number = order.order_number
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)

        def history(*, provider_order_id):
            if provider_order_id == first.provider_order_id:
                return [_capture(first, first.provider_payment_id)]
            raise PaymentProviderUnavailable("Simulated outage")

        monkeypatch.setattr(audit_upi_payments, "list_razorpay_order_payments", history)
        report = audit_upi_payments.audit_paid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == order_number)
        assert finding["result"] == "provider_unavailable"


def test_audit_rejects_capture_with_missing_payment_identifier(monkeypatch):
    with session() as db:
        order = make_order(db, with_paid_attempt=False)
        attempt = PaymentAttempt(
            order_id=order.id, provider="razorpay",
            provider_order_id=f"order_{uuid4().hex}",
            status="paid", amount=order.total, currency="INR",
        )
        db.add(attempt)
        db.commit()
        order_number = order.order_number
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments",
            lambda **_: [{
                "id": None, "order_id": attempt.provider_order_id,
                "status": "captured", "amount": 12000, "currency": "INR",
            }],
        )
        report = audit_upi_payments.audit_paid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == order_number)
        assert finding["result"] == "capture_mismatch"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("amount", Decimal("119.00")),
        ("currency", "USD"),
        ("status", "attempted"),
    ],
)
def test_audit_flags_inconsistent_local_ledger_despite_valid_capture(monkeypatch, field, value):
    with session() as db:
        order = make_order(db)
        attempt = db.scalar(
            select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
        )
        setattr(attempt, field, value)
        db.commit()
        order_number = order.order_number
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments",
            lambda **_: [_capture(attempt, attempt.provider_payment_id)],
        )

        report = audit_upi_payments.audit_paid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == order_number)
        assert finding["result"] == "capture_mismatch"


def test_audit_does_not_ignore_attempts_from_other_payment_providers(monkeypatch):
    with session() as db:
        order = make_order(db)
        razorpay_attempt = db.scalar(
            select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
        )
        db.add(PaymentAttempt(
            order_id=order.id, provider="unrecognised_provider",
            status="attempted", amount=order.total, currency="INR",
        ))
        db.commit()
        order_number = order.order_number
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments",
            lambda **_: [_capture(razorpay_attempt, razorpay_attempt.provider_payment_id)],
        )
        report = audit_upi_payments.audit_paid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == order_number)
        assert finding["result"] == "capture_mismatch"
        assert report["requires_review"] >= 1


@pytest.mark.parametrize(("extra_status", "expected"), [
    ("authorized", "provider_ambiguous"),
    ("created", "provider_ambiguous"),
    ("refunded", "provider_ambiguous"),
    ("unexpected", "provider_ambiguous"),
    ("failed", "verified_capture"),
])
def test_audit_does_not_hide_unsettled_provider_payment_behind_capture(
    monkeypatch, extra_status, expected,
):
    with session() as db:
        order = make_order(db)
        attempt = db.scalar(
            select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
        )
        db.commit()
        order_number = order.order_number
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments",
            lambda **_: [
                _capture(attempt, attempt.provider_payment_id),
                {
                    "id": f"pay_{uuid4().hex}",
                    "order_id": attempt.provider_order_id,
                    "status": extra_status,
                    "amount": 12000,
                    "currency": "INR",
                },
            ],
        )
        report = audit_upi_payments.audit_paid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == order_number)
        assert finding["result"] == expected


def test_audit_flags_second_paid_attempt_missing_provider_payment_id(monkeypatch):
    with session() as db:
        order = make_order(db)
        first = db.scalar(
            select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
        )
        second = PaymentAttempt(
            order_id=order.id, provider="razorpay",
            provider_order_id=f"order_{uuid4().hex}",
            status="paid", amount=order.total, currency="INR",
            provider_payment_id=None,
        )
        db.add(second)
        db.commit()
        order_number = order.order_number
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments",
            lambda *, provider_order_id: (
                [_capture(first, first.provider_payment_id)]
                if provider_order_id == first.provider_order_id else []
            ),
        )
        report = audit_upi_payments.audit_paid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == order_number)
        assert finding["result"] == "capture_mismatch"


@pytest.mark.parametrize("bad_failed_payment", [
    {"status": "failed", "order_id": "wrong_order", "id": "pay_failed", "amount": 12000, "currency": "INR"},
    {"status": "failed", "id": None, "amount": 12000, "currency": "INR"},
    {"status": "failed", "id": "pay_failed", "amount": 12000, "currency": "USD"},
    {"status": "failed", "id": "pay_failed", "amount": "12000", "currency": "INR"},
])
def test_audit_rejects_malformed_failed_history_even_with_valid_capture(
    monkeypatch, bad_failed_payment,
):
    with session() as db:
        order = make_order(db)
        attempt = db.scalar(
            select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
        )
        db.commit()
        order_number = order.order_number
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments",
            lambda **_: [
                _capture(attempt, attempt.provider_payment_id),
                bad_failed_payment,
            ],
        )
        report = audit_upi_payments.audit_paid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == order_number)
        assert finding["result"] == "capture_mismatch"
