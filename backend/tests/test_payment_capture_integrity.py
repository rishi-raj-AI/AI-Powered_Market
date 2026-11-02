"""Provider-authoritative payment tests for the *active* hardened routes.

Never call Razorpay: all provider reads are stubbed and the database is the CI
test database. A valid HMAC callback alone must not mark money as captured.
"""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.routes import payment_hardening
from app.models.integrations import PaymentAttempt, PaymentRefund
from app.models.orders import OrderStatus, PaymentStatus
from app.schemas.integrations import PaymentVerifyRequest
from app.services.refunds import refund_idempotency_key
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
        assert settlements == [order.id]


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


def test_late_capture_after_return_creates_refund_not_settlement(monkeypatch):
    with session() as db:
        customer, order, attempt = _context(db)
        order.status = OrderStatus.RETURNED
        db.commit()
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
        result = _verify(db, customer, attempt)
        db.refresh(order)
        db.refresh(attempt)
        refund = db.query(PaymentRefund).filter(PaymentRefund.order_id == order.id).one()
        assert result.payment_status == "refund_pending"
        assert order.status == OrderStatus.RETURNED
        assert order.payment_status == PaymentStatus.REFUND_PENDING
        assert attempt.status == "paid"
        assert refund.provider_payment_id == "pay_test_capture_12345"
        assert refund.reason == payment_hardening.REFUND_REASON_RETURNED
        assert settlements == []


def test_late_capture_after_cancellation_creates_dispatchable_refund(monkeypatch):
    with session() as db:
        customer, order, attempt = _context(db)
        order.status = OrderStatus.CANCELLED
        db.commit()
        monkeypatch.setattr(payment_hardening, "verify_razorpay_signature", lambda **_: True)
        monkeypatch.setattr(
            payment_hardening, "fetch_razorpay_payment",
            lambda *, provider_payment_id: _payment(attempt, provider_payment_id),
        )
        monkeypatch.setattr(
            payment_hardening, "ensure_settlement_entry",
            lambda *_: pytest.fail("Cancelled order must not settle"),
        )
        result = _verify(db, customer, attempt)
        refund = db.query(PaymentRefund).filter(PaymentRefund.order_id == order.id).one()
        assert result.payment_status == "refund_pending"
        assert refund.provider_payment_id == "pay_test_capture_12345"
        assert refund.payment_attempt_id == attempt.id
        assert refund.reason == payment_hardening.REFUND_REASON_ORPHANED_CAPTURE
        assert order.status == OrderStatus.CANCELLED


def test_late_capture_links_existing_refund_without_payment_id(monkeypatch):
    with session() as db:
        customer, order, attempt = _context(db)
        order.status = OrderStatus.CANCELLED
        order.payment_status = PaymentStatus.REFUND_PENDING
        refund = PaymentRefund(
            order_id=order.id, provider="razorpay",
            provider_payment_id=None, amount=order.total, currency="INR",
            status="requested", reason=payment_hardening.REFUND_REASON_ORPHANED_CAPTURE,
            idempotency_key=refund_idempotency_key(order.id),
            requested_at=datetime.now(timezone.utc),
        )
        db.add(refund)
        db.commit()
        monkeypatch.setattr(payment_hardening, "verify_razorpay_signature", lambda **_: True)
        monkeypatch.setattr(
            payment_hardening, "fetch_razorpay_payment",
            lambda *, provider_payment_id: _payment(attempt, provider_payment_id),
        )
        monkeypatch.setattr(
            payment_hardening, "ensure_settlement_entry",
            lambda *_: pytest.fail("Refund-pending order must not settle"),
        )
        result = _verify(db, customer, attempt)
        db.refresh(refund)
        assert result.payment_status == "refund_pending"
        assert refund.provider_payment_id == "pay_test_capture_12345"
        assert refund.payment_attempt_id == attempt.id
        assert refund.status == "requested"


def test_second_capture_cannot_replace_first_payment_id(monkeypatch):
    with session() as db:
        customer, order, attempt = _context(db)
        monkeypatch.setattr(payment_hardening, "verify_razorpay_signature", lambda **_: True)
        monkeypatch.setattr(
            payment_hardening, "fetch_razorpay_payment",
            lambda *, provider_payment_id: _payment(attempt, provider_payment_id),
        )
        monkeypatch.setattr(payment_hardening, "ensure_settlement_entry", lambda *_: None)
        _verify(db, customer, attempt)
        with pytest.raises(HTTPException) as exc:
            _verify(db, customer, attempt, payment_id="pay_second_capture_67890")
        assert exc.value.status_code == 409
        db.refresh(attempt)
        db.refresh(order)
        assert attempt.provider_payment_id == "pay_test_capture_12345"
        assert order.payment_status == PaymentStatus.PAID


def test_capture_on_second_attempt_requires_manual_reconciliation(monkeypatch):
    with session() as db:
        customer, order, first_attempt = _context(db)
        second_attempt = PaymentAttempt(
            order_id=order.id, provider="razorpay",
            provider_order_id=f"order_{uuid4().hex}",
            status="attempted", amount=Decimal("120.00"), currency="INR",
        )
        db.add(second_attempt)
        db.commit()
        monkeypatch.setattr(payment_hardening, "verify_razorpay_signature", lambda **_: True)
        monkeypatch.setattr(
            payment_hardening, "fetch_razorpay_payment",
            lambda *, provider_payment_id: _payment(
                first_attempt if provider_payment_id == "pay_test_capture_12345" else second_attempt,
                provider_payment_id,
            ),
        )
        monkeypatch.setattr(payment_hardening, "ensure_settlement_entry", lambda *_: None)
        _verify(db, customer, first_attempt)
        with pytest.raises(HTTPException) as exc:
            _verify(db, customer, second_attempt, payment_id="pay_second_attempt_67890")
        assert exc.value.status_code == 409
        db.refresh(first_attempt)
        db.refresh(second_attempt)
        assert first_attempt.status == "paid"
        assert second_attempt.status == "attempted"
        assert second_attempt.provider_payment_id is None



def test_order_paid_webhook_without_payment_entity_reconciles_one_capture(monkeypatch):
    with session() as db:
        _customer, order, attempt = _context(db)
        payment_id = f"pay_{uuid4().hex}"
        monkeypatch.setattr(
            payment_hardening, "list_razorpay_order_payments",
            lambda **_: [_payment(attempt, payment_id)],
        )
        monkeypatch.setattr(
            payment_hardening, "fetch_razorpay_payment",
            lambda *, provider_payment_id: _payment(attempt, provider_payment_id),
        )
        settlements = []
        monkeypatch.setattr(
            payment_hardening, "ensure_settlement_entry",
            lambda _db, _order: settlements.append(_order.id),
        )
        monkeypatch.setattr(payment_hardening, "_notify_payment_captured", lambda *_: None)
        payload = {
            "event": "order.paid",
            "payload": {"order": {"entity": {"id": attempt.provider_order_id}}},
        }
        assert payment_hardening._process_event(db, payload) is True
        db.commit()
        db.refresh(order)
        db.refresh(attempt)
        assert order.payment_status == PaymentStatus.PAID
        assert attempt.provider_payment_id == payment_id
        assert settlements == [order.id]
        assert payment_hardening._process_event(db, payload) is True
        db.commit()
        assert settlements == [order.id]


@pytest.mark.parametrize("secondary_status", ["authorized", "created", "refunded", "processing", None])
def test_order_paid_webhook_defers_ambiguous_provider_history(monkeypatch, secondary_status):
    with session() as db:
        _customer, order, attempt = _context(db)
        payment_id = f"pay_{uuid4().hex}"
        monkeypatch.setattr(
            payment_hardening, "list_razorpay_order_payments",
            lambda **_: [
                _payment(attempt, payment_id),
                _payment(attempt, f"pay_{uuid4().hex}", status=secondary_status),
            ],
        )
        monkeypatch.setattr(
            payment_hardening, "fetch_razorpay_payment",
            lambda **_: pytest.fail("Ambiguous history must not confirm capture"),
        )
        payload = {
            "event": "order.paid",
            "payload": {"order": {"entity": {"id": attempt.provider_order_id}}},
        }
        assert payment_hardening._process_event(db, payload) is False
        db.rollback()
        db.refresh(order)
        assert order.payment_status == PaymentStatus.PENDING


@pytest.mark.parametrize("invalid_failed_fields", [
    {"id": ""},
    {"id": None},
    {"order_id": "order_wrong"},
    {"amount": 11999},
    {"amount": None},
    {"currency": "USD"},
    {"currency": None},
])
def test_order_paid_defers_malformed_failed_secondary_payment(
    monkeypatch, invalid_failed_fields,
):
    """An unrelated or malformed failed row cannot certify a single capture."""
    with session() as db:
        _customer, order, attempt = _context(db)
        failed = _payment(
            attempt, f"pay_failed_{uuid4().hex}", status="failed",
            **invalid_failed_fields,
        )
        monkeypatch.setattr(
            payment_hardening, "list_razorpay_order_payments",
            lambda **_: [_payment(attempt, f"pay_capture_{uuid4().hex}"), failed],
        )
        monkeypatch.setattr(
            payment_hardening, "fetch_razorpay_payment",
            lambda **_: pytest.fail("Malformed provider history must defer capture"),
        )
        payload = {
            "event": "order.paid",
            "payload": {"order": {"entity": {"id": attempt.provider_order_id}}},
        }
        assert payment_hardening._process_event(db, payload) is False
        db.rollback()
        db.refresh(order)
        assert order.payment_status == PaymentStatus.PENDING


def test_order_paid_accepts_capture_with_wellformed_failed_retry(monkeypatch):
    with session() as db:
        _customer, order, attempt = _context(db)
        captured_id = f"pay_capture_{uuid4().hex}"
        monkeypatch.setattr(
            payment_hardening, "list_razorpay_order_payments",
            lambda **_: [
                _payment(attempt, captured_id),
                _payment(attempt, f"pay_failed_{uuid4().hex}", status="failed"),
            ],
        )
        monkeypatch.setattr(
            payment_hardening, "fetch_razorpay_payment",
            lambda *, provider_payment_id: _payment(attempt, provider_payment_id),
        )
        monkeypatch.setattr(payment_hardening, "ensure_settlement_entry", lambda *_: None)
        monkeypatch.setattr(payment_hardening, "_notify_payment_captured", lambda *_: None)
        payload = {
            "event": "order.paid",
            "payload": {"order": {"entity": {"id": attempt.provider_order_id}}},
        }
        assert payment_hardening._process_event(db, payload) is True
        db.commit()
        db.refresh(order)
        assert order.payment_status == PaymentStatus.PAID
