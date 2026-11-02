"""Refund webhook identity checks: signed events must match the recorded obligation."""
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import event

from app.api.v1.routes.payment_hardening import _process_refund_event
from app.models.orders import PaymentStatus
from app.services.refunds import REFUND_REASON_CANCELLED, ensure_refund_request, apply_provider_refund_result
from app.services.payments import PaymentProviderError
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
    {"currency": None},
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


def test_refund_webhook_without_currency_is_not_authoritative():
    """A signed event still needs a complete refund transaction identity."""
    with session() as db:
        order, refund = _context(db)
        payload = _payload(refund)
        del payload["payload"]["refund"]["entity"]["currency"]
        assert _process_refund_event(db, payload) is False
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
        late_failure = _payload(refund, status="failed")
        late_failure["event"] = "refund.failed"
        assert _process_refund_event(db, late_failure) is True
        db.commit()
        db.refresh(order)
        db.refresh(refund)
        assert order.payment_status == PaymentStatus.REFUNDED
        assert refund.status == "succeeded"
        assert refund.provider_status == "processed"


@pytest.mark.parametrize("event_name,provider_status", [
    ("refund.processed", "failed"),
    ("refund.processed", "pending"),
    ("refund.failed", "processed"),
    ("refund.failed", "pending"),
    ("refund.processed", "unrecognized"),
    ("refund.failed", None),
])
def test_refund_webhook_defers_contradictory_or_unknown_outcome(
    event_name, provider_status,
):
    """A signed but inconsistent event must not settle or requeue money."""
    with session() as db:
        order, refund = _context(db)
        payload = _payload(refund, status=provider_status)
        payload["event"] = event_name
        assert _process_refund_event(db, payload) is False
        db.commit()
        db.refresh(order)
        db.refresh(refund)
        assert order.payment_status == PaymentStatus.REFUND_PENDING
        assert refund.status == "requested"
        assert refund.provider_status is None


def test_unknown_refund_id_with_known_payment_cannot_replace_existing_refund():
    with session() as db:
        order, refund = _context(db)
        assert _process_refund_event(db, _payload(refund, id=f"rfnd_{uuid4().hex}")) is False
        db.commit()
        db.refresh(order)
        assert order.payment_status == PaymentStatus.REFUND_PENDING


def test_direct_provider_result_cannot_reverse_completed_refund():
    with session() as db:
        order, refund = _context(db)
        apply_provider_refund_result(db, refund, {
            "id": refund.provider_refund_id, "status": "processed",
        })
        db.commit()
        apply_provider_refund_result(db, refund, {
            "id": refund.provider_refund_id, "status": "failed",
        })
        db.commit()
        db.refresh(order)
        db.refresh(refund)
        assert refund.status == "succeeded"
        assert order.payment_status == PaymentStatus.REFUNDED


def test_direct_provider_result_rejects_conflicting_refund_id():
    with session() as db:
        order, refund = _context(db)
        with pytest.raises(PaymentProviderError):
            apply_provider_refund_result(db, refund, {
                "id": f"rfnd_{uuid4().hex}", "status": "processed",
            })
        db.rollback()
        db.refresh(order)
        assert order.payment_status == PaymentStatus.REFUND_PENDING


@pytest.mark.parametrize("known_refund_id", [True, False])
def test_refund_webhook_locks_order_before_refund(known_refund_id):
    """Avoid a PostgreSQL deadlock with cancellation's order-first locking."""
    with session() as db:
        order, refund = _context(db)
        if not known_refund_id:
            refund.provider_refund_id = None
            db.commit()
        observed = []

        def record_lock(orm_execute_state):
            stmt = orm_execute_state.statement
            if getattr(stmt, "_for_update_arg", None) is None:
                return
            sql = str(stmt)
            if "FROM orders" in sql:
                observed.append("order")
            elif "FROM payment_refunds" in sql:
                observed.append("refund")

        event.listen(db, "do_orm_execute", record_lock)
        try:
            assert _process_refund_event(
                db, _payload(refund, id=refund.provider_refund_id or f"rfnd_{uuid4().hex}")
            ) is True
            db.commit()
        finally:
            event.remove(db, "do_orm_execute", record_lock)
        assert observed[:2] == ["order", "refund"]
        db.refresh(order)
        assert order.payment_status == PaymentStatus.REFUNDED
