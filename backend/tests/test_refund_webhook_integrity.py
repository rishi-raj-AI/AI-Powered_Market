"""Refund webhook identity checks: signed events must match the recorded obligation."""
from decimal import Decimal
from uuid import uuid4

import pytest

from app.api.v1.routes.payment_hardening import _process_refund_event
from app.models.orders import PaymentStatus
from app.services.refunds import REFUND_REASON_CANCELLED, ensure_refund_request
from tests.factories import make_order, session


def _payload(refund, **overrides):
    entity = {
        "id": refund.provider_refund_id,
        "payment_id": refund.provider_payment_id,
        "amount": int(Decimal(refund.amount) * 100),
        "currency": refund.currency,
        "status": "processed",
    }
    entity.update(overrides)
    return {"event": "refund.processed", "payload": {"refund": {"entity": entity}}}


def _context(db):
    order = make_order(db, payment_status=PaymentStatus.PAID)
    db.commit()
    refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
    assert refund is not None and refund.provider_payment_id
    refund.provider_refund_id = f"rfnd_{uuid4().hex}"
    db.commit()
    return order, refund


@pytest.mark.parametrize("change", [
    {"payment_id": "pay_another_payment"},
    {"id": "rfnd_another_refund"},
    {"amount": 1},
    {"currency": "USD"},
    {"amount": None},
    {"payment_id": None},
])
def test_mismatched_refund_webhook_cannot_mark_order_refunded(change):
    with session() as db:
        order, refund = _context(db)
        assert _process_refund_event(db, _payload(refund, **change)) is False
        db.commit()
        db.refresh(order)
        db.refresh(refund)
        assert order.payment_status == PaymentStatus.REFUND_PENDING
        assert refund.status == "requested"


def test_matching_refund_webhook_marks_order_refunded():
    with session() as db:
        order, refund = _context(db)
        assert _process_refund_event(db, _payload(refund)) is True
        db.commit()
        db.refresh(order)
        db.refresh(refund)
        assert order.payment_status == PaymentStatus.REFUNDED
        assert refund.status == "succeeded"


def test_late_failed_webhook_cannot_reverse_processed_refund():
    with session() as db:
        order, refund = _context(db)
        assert _process_refund_event(db, _payload(refund)) is True
        db.commit()
        assert _process_refund_event(db, _payload(refund, status="failed")) is True
        db.commit()
        db.refresh(order)
        db.refresh(refund)
        assert order.payment_status == PaymentStatus.REFUNDED
        assert refund.status == "succeeded"
        assert refund.provider_status == "processed"


def test_unknown_refund_id_with_known_payment_cannot_replace_existing_refund():
    with session() as db:
        order, refund = _context(db)
        assert _process_refund_event(db, _payload(refund, id=f"rfnd_{uuid4().hex}")) is False
        db.commit()
        db.refresh(order)
        assert order.payment_status == PaymentStatus.REFUND_PENDING
