"""Read-only audit of unpaid UPI orders must not conceal captured money."""
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.integrations import PaymentAttempt
from app.models.orders import PaymentStatus
from app.scripts import audit_upi_payments
from app.services.payments import PaymentProviderUnavailable
from tests.factories import make_order, session


def _attempt(db, order, *, status="attempted", provider="razorpay", payment_id=None):
    attempt = PaymentAttempt(
        order_id=order.id,
        provider=provider,
        provider_order_id=f"order_{uuid4().hex}",
        provider_payment_id=payment_id,
        status=status,
        amount=order.total,
        currency="INR",
    )
    db.add(attempt)
    db.flush()
    return attempt


def _payment(attempt, status="captured", *, payment_id=None, amount=12000):
    return {
        "id": payment_id or f"pay_{uuid4().hex}",
        "order_id": attempt.provider_order_id,
        "status": status,
        "amount": amount,
        "currency": "INR",
    }


@pytest.mark.parametrize(
    ("provider_status", "expected"),
    [
        ("captured", "unexpected_capture"),
        ("authorized", "provider_ambiguous"),
        ("created", "provider_ambiguous"),
        ("refunded", "provider_ambiguous"),
        ("failed", "no_capture_found"),
    ],
)
def test_unpaid_audit_classifies_provider_history(monkeypatch, provider_status, expected):
    with session() as db:
        order = make_order(
            db, payment_status=PaymentStatus.PENDING, with_paid_attempt=False
        )
        attempt = _attempt(db, order)
        db.commit()
        number = order.order_number
        attempt_id = attempt.id
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments",
            lambda **_: [_payment(attempt, provider_status)],
        )

        report = audit_upi_payments.audit_unpaid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == number)
        assert finding["result"] == expected
        assert report["requires_review"] >= (expected != "no_capture_found")
        # The audit owns and closes its read-only session. Verify persisted
        # state in a new session instead of dereferencing a detached ORM row.
        with session() as verify_db:
            assert verify_db.scalar(
                select(PaymentAttempt.status).where(PaymentAttempt.id == attempt_id)
            ) == "attempted"


@pytest.mark.parametrize("amount", [12000.0, "12000", True])
def test_paid_audit_rejects_noninteger_capture_amount(monkeypatch, amount):
    with session() as db:
        order = make_order(db)
        attempt = db.scalar(select(PaymentAttempt).where(PaymentAttempt.order_id == order.id))
        db.commit()
        number = order.order_number
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments",
            lambda **_: [_payment(attempt, payment_id=attempt.provider_payment_id, amount=amount)],
        )
        report = audit_upi_payments.audit_paid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == number)
        assert finding["result"] == "capture_mismatch"


def test_unpaid_audit_flags_multiple_captures_and_keeps_order_unpaid(monkeypatch):
    with session() as db:
        order = make_order(
            db, payment_status=PaymentStatus.FAILED, with_paid_attempt=False
        )
        attempt = _attempt(db, order, status="failed")
        db.commit()
        number = order.order_number
        order_id = order.id
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments",
            lambda **_: [_payment(attempt), _payment(attempt)],
        )
        report = audit_upi_payments.audit_unpaid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == number)
        assert finding["result"] == "multiple_captures"
        assert finding["provider_capture_count"] == 2
        with session() as verify_db:
            assert verify_db.scalar(
                select(type(order).payment_status).where(type(order).id == order_id)
            ) == PaymentStatus.FAILED


@pytest.mark.parametrize(
    ("local_status", "payment_id", "expected"),
    [
        ("paid", None, "local_capture_evidence"),
        ("failed", "pay_local_capture", "local_capture_evidence"),
        ("authorized", None, "provider_ambiguous"),
        ("processing", None, "provider_ambiguous"),
        ("failed", None, "no_capture_found"),
    ],
)
def test_unpaid_audit_preserves_local_uncertainty(
    monkeypatch, local_status, payment_id, expected,
):
    with session() as db:
        order = make_order(
            db, payment_status=PaymentStatus.PENDING, with_paid_attempt=False
        )
        _attempt(db, order, status=local_status, payment_id=payment_id)
        db.commit()
        number = order.order_number
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(audit_upi_payments, "list_razorpay_order_payments", lambda **_: [])
        report = audit_upi_payments.audit_unpaid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == number)
        assert finding["result"] == expected


def test_unpaid_audit_does_not_treat_provider_outage_as_unpaid(monkeypatch):
    with session() as db:
        order = make_order(
            db, payment_status=PaymentStatus.PENDING, with_paid_attempt=False
        )
        _attempt(db, order)
        db.commit()
        number = order.order_number
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        def outage(**_):
            raise PaymentProviderUnavailable("simulated")
        monkeypatch.setattr(audit_upi_payments, "list_razorpay_order_payments", outage)
        report = audit_upi_payments.audit_unpaid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == number)
        assert finding["result"] == "provider_unavailable"


def test_unpaid_audit_requires_review_when_no_payment_attempt_exists(monkeypatch):
    with session() as db:
        order = make_order(
            db, payment_status=PaymentStatus.PENDING, with_paid_attempt=False
        )
        db.commit()
        number = order.order_number
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        report = audit_upi_payments.audit_unpaid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == number)
        assert finding["result"] == "missing_payment_attempt"


@pytest.mark.parametrize(
    ("provider", "currency", "provider_order", "expected"),
    [
        ("other_provider", "INR", True, "payment_history_mismatch"),
        ("razorpay", "USD", True, "payment_history_mismatch"),
        ("razorpay", "INR", False, "payment_history_mismatch"),
    ],
)
def test_unpaid_audit_quarantines_unverifiable_attempts(
    monkeypatch, provider, currency, provider_order, expected,
):
    with session() as db:
        order = make_order(
            db, payment_status=PaymentStatus.FAILED, with_paid_attempt=False
        )
        attempt = _attempt(db, order, status="failed", provider=provider)
        attempt.currency = currency
        if not provider_order:
            attempt.provider_order_id = None
        db.commit()
        number = order.order_number
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        def unexpected_provider_read(**_):
            pytest.fail("Unverifiable attempts must not be treated as safe provider histories")
        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments", unexpected_provider_read
        )
        report = audit_upi_payments.audit_unpaid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == number)
        assert finding["result"] == expected


def test_unpaid_audit_rejects_malformed_capture_money(monkeypatch):
    with session() as db:
        order = make_order(
            db, payment_status=PaymentStatus.PENDING, with_paid_attempt=False
        )
        attempt = _attempt(db, order)
        db.commit()
        number = order.order_number
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments",
            lambda **_: [_payment(attempt, amount="12000")],
        )
        report = audit_upi_payments.audit_unpaid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == number)
        # A malformed capture still means the provider might have moved money.
        assert finding["result"] == "unexpected_capture"
        assert finding["provider_capture_count"] == 1
