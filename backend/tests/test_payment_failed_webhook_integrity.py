"""Signed failure webhooks cannot corrupt capture evidence or another intent.

Uses only disposable PostgreSQL test records and synthetic webhook entities.
No Razorpay API calls, credentials, or production data.
"""
from decimal import Decimal
from uuid import uuid4

import pytest

from app.api.v1.routes import payment_hardening
from app.models.integrations import PaymentAttempt
from app.models.orders import PaymentStatus
from tests.factories import make_order, session


def _context(db):
    order = make_order(
        db, payment_status=PaymentStatus.PENDING, with_paid_attempt=False,
    )
    attempt = PaymentAttempt(
        order_id=order.id,
        provider="razorpay",
        provider_order_id=f"order_{uuid4().hex}",
        status="attempted",
        amount=Decimal("120.00"),
        currency="INR",
    )
    db.add(attempt)
    db.commit()
    return order, attempt


def _failed_event(attempt, **changes):
    entity = {
        "id": f"pay_failed_{uuid4().hex}",
        "order_id": attempt.provider_order_id,
        "amount": 12000,
        "currency": "INR",
        "status": "failed",
    }
    entity.update(changes)
    return {"event": "payment.failed", "payload": {"payment": {"entity": entity}}}


def test_well_formed_failure_updates_only_unpaid_attempt():
    with session() as db:
        order, attempt = _context(db)
        assert payment_hardening._process_event(db, _failed_event(attempt)) is True
        db.flush()
        assert order.payment_status == PaymentStatus.FAILED
        assert attempt.status == "failed"


@pytest.mark.parametrize("changes", [
    {"id": ""},
    {"id": None},
    {"order_id": "order_unrelated"},
    {"order_id": None},
    {"amount": 11999},
    {"amount": None},
    {"amount": True},
    {"currency": "USD"},
    {"currency": None},
    {"status": "authorized"},
    {"status": None},
])
def test_malformed_or_unrelated_failure_is_deferred_without_mutation(changes):
    with session() as db:
        order, attempt = _context(db)
        assert payment_hardening._process_event(
            db, _failed_event(attempt, **changes),
        ) is False
        db.flush()
        assert order.payment_status == PaymentStatus.PENDING
        assert attempt.status == "attempted"


def test_order_only_failure_cannot_mark_order_failed():
    with session() as db:
        order, attempt = _context(db)
        event = {
            "event": "payment.failed",
            "payload": {"order": {"entity": {"id": attempt.provider_order_id}}},
        }
        assert payment_hardening._process_event(db, event) is False
        db.flush()
        assert order.payment_status == PaymentStatus.PENDING
        assert attempt.status == "attempted"


def test_failure_without_provider_order_id_remains_unprocessed():
    with session() as db:
        order, attempt = _context(db)
        event = {
            "event": "payment.failed",
            "payload": {"payment": {"entity": {
                "id": "pay_failed_without_order", "status": "failed",
                "amount": 12000, "currency": "INR",
            }}},
        }
        assert payment_hardening._process_event(db, event) is False
        db.flush()
        assert order.payment_status == PaymentStatus.PENDING
        assert attempt.status == "attempted"


@pytest.mark.parametrize("capture_evidence", ["paid_status", "provider_payment_id"])
def test_failure_on_second_attempt_does_not_hide_earlier_capture(capture_evidence):
    """A stale PENDING order may already contain capture evidence elsewhere."""
    with session() as db:
        order, earlier = _context(db)
        if capture_evidence == "paid_status":
            earlier.status = "paid"
        else:
            earlier.provider_payment_id = f"pay_captured_{uuid4().hex}"
        later = PaymentAttempt(
            order_id=order.id, provider="razorpay",
            provider_order_id=f"order_{uuid4().hex}",
            status="attempted", amount=order.total, currency="INR",
        )
        db.add(later)
        db.commit()
        assert payment_hardening._process_event(db, _failed_event(later)) is True
        db.flush()
        assert later.status == "failed"
        assert order.payment_status == PaymentStatus.PENDING
        db.rollback()


@pytest.mark.parametrize("capture_evidence", ["paid_status", "provider_payment_id"])
def test_late_failure_preserves_locally_recorded_capture(capture_evidence):
    # Simulate a legacy inconsistent record: attempt has capture evidence but
    # the order-level status still says PENDING. Failure must not erase it.
    with session() as db:
        order, attempt = _context(db)
        if capture_evidence == "paid_status":
            attempt.status = "paid"
        else:
            attempt.provider_payment_id = f"pay_captured_{uuid4().hex}"
        db.commit()
        assert payment_hardening._process_event(db, _failed_event(attempt)) is True
        db.flush()
        assert order.payment_status == PaymentStatus.PENDING
        assert attempt.status == ("paid" if capture_evidence == "paid_status" else "attempted")
        assert (attempt.provider_payment_id is not None) == (
            capture_evidence == "provider_payment_id"
        )
