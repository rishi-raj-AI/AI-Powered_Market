"""Provider-authoritative payment tests for the *active* hardened routes.

Never call Razorpay: all provider reads are stubbed and the database is the CI
test database. A valid HMAC callback alone must not mark money as captured.
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.routes import payment_hardening
from app.models.integrations import PaymentAttempt
from app.models.orders import PaymentStatus
from app.schemas.integrations import PaymentVerifyRequest
from tests.factories import make_order, make_user, session


def _context(db):
    customer = make_user(db)
    order = make_order(
        db, customer=customer, payment_status=PaymentStatus.PENDING,
        with_paid_attempt=False,
    )
    attempt = PaymentAttempt(
        order_id=order.id, provider="razorpay",
        provider_order_id=f"order_{uuid4().hex}",
        status="attempted", amount=Decimal("120.00"), currency="INR",
    )
    db.add(attempt)
    db.commit()
    return customer, order, attempt


def _payment(attempt, payment_id, **overrides):
    result = {
        "id": payment_id,
        "order_id": attempt.provider_order_id,
        "amount": 12000,
        "currency": "INR",
        "status": "captured",
    }
    result.update(overrides)
    return result


def _verify(db, customer, attempt, payment_id="pay_test_capture_12345"):
    return payment_hardening.hardened_verify_payment(
        PaymentVerifyRequest(
            payment_attempt_id=attempt.id,
            razorpay_payment_id=payment_id,
            razorpay_signature="s" * 64,
        ),
        db=db, user=customer,
    )


def test_valid_signature_without_capture_cannot_mark_order_paid(monkeypatch):
    with session() as db:
        customer, order, attempt = _context(db)
        monkeypatch.setattr(payment_hardening, "verify_razorpay_signature", lambda **_: True)
        monkeypatch.setattr(
            payment_hardening, "fetch_razorpay_payment",
            lambda *, provider_payment_id: _payment(
                attempt, provider_payment_id, status="authorized",
            ),
        )
        with pytest.raises(HTTPException) as exc:
            _verify(db, customer, attempt)
        assert exc.value.status_code == 409
        db.refresh(order)
        db.refresh(attempt)
        assert order.payment_status == PaymentStatus.PENDING
        assert attempt.status == "attempted"


@pytest.mark.parametrize("mismatch", [
    {"amount": 11999},
    {"currency": "USD"},
    {"order_id": "order_different"},
    {"id": "pay_different"},
])
def test_mismatched_capture_cannot_mark_order_paid(monkeypatch, mismatch):
    with session() as db:
        customer, order, attempt = _context(db)
        monkeypatch.setattr(payment_hardening, "verify_razorpay_signature", lambda **_: True)
        monkeypatch.setattr(
            payment_hardening, "fetch_razorpay_payment",
            lambda *, provider_payment_id: _payment(attempt, provider_payment_id, **mismatch),
        )
        with pytest.raises(HTTPException) as exc:
            _verify(db, customer, attempt)
        assert exc.value.status_code == 409
        db.refresh(order)
        assert order.payment_status == PaymentStatus.PENDING


def test_invalid_callback_signature_does_not_change_payment_status(monkeypatch):
    with session() as db:
        customer, order, attempt = _context(db)
        monkeypatch.setattr(payment_hardening, "verify_razorpay_signature", lambda **_: False)
        monkeypatch.setattr(
            payment_hardening, "fetch_razorpay_payment",
            lambda **_: pytest.fail("Provider must not be queried for invalid signatures"),
        )
        with pytest.raises(HTTPException) as exc:
            _verify(db, customer, attempt)
        assert exc.value.status_code == 400
        db.refresh(order)
        db.refresh(attempt)
        assert order.payment_status == PaymentStatus.PENDING
        assert attempt.status == "attempted"


def test_confirmed_capture_marks_paid_and_duplicate_callback_is_idempotent(monkeypatch):
    with session() as db:
        customer, order, attempt = _context(db)
        monkeypatch.setattr(payment_hardening, "verify_razorpay_signature", lambda **_: True)
        monkeypatch.setattr(
            payment_hardening, "fetch_razorpay_payment",
            lambda *, provider_payment_id: _payment(attempt, provider_payment_id),
        )
        settlements = []
        monkeypatch.setattr(
            payment_hardening, "ensure_settlement_entry",
            lambda _db, _order: settlements.append(_order.id),
        )
        first = _verify(db, customer, attempt)
        second = _verify(db, customer, attempt)
        assert first.payment_status == "paid"
        assert second.payment_status == "paid"
        db.refresh(order)
        db.refresh(attempt)
        assert order.payment_status == PaymentStatus.PAID
        assert attempt.provider_payment_id == "pay_test_capture_12345"
        assert attempt.status == "paid"
        assert settlements == [order.id, order.id]


def test_success_webhook_requires_capture_and_ignores_late_failure(monkeypatch):
    with session() as db:
        _customer, order, attempt = _context(db)
        provider_payment_id = "pay_webhook_capture_123"
        event = {
            "event": "payment.captured",
            "payload": {
                "payment": {"entity": {
                    "id": provider_payment_id,
                    "order_id": attempt.provider_order_id,
                }}
            },
        }
        monkeypatch.setattr(
            payment_hardening, "fetch_razorpay_payment",
            lambda *, provider_payment_id: _payment(
                attempt, provider_payment_id, status="authorized",
            ),
        )
        monkeypatch.setattr(payment_hardening, "ensure_settlement_entry", lambda *_: None)
        payment_hardening._process_event(db, event)
        db.flush()
        assert order.payment_status == PaymentStatus.PENDING

        monkeypatch.setattr(
            payment_hardening, "fetch_razorpay_payment",
            lambda *, provider_payment_id: _payment(attempt, provider_payment_id),
        )
        payment_hardening._process_event(db, event)
        db.flush()
        assert order.payment_status == PaymentStatus.PAID

        payment_hardening._process_event(db, {
            "event": "payment.failed",
            "payload": {"payment": {"entity": {
                "id": provider_payment_id,
                "order_id": attempt.provider_order_id,
            }}},
        })
        db.flush()
        assert order.payment_status == PaymentStatus.PAID
        db.rollback()
