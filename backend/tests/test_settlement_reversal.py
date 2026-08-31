"""P0-B: a refunded order must not leave the merchant queued to be paid.

``ensure_settlement_entry`` used to be create-only, so this sequence paid the
merchant for money the customer had already got back:

    UPI paid -> settlement created -> customer cancels -> refund -> entry lives on
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from app.models.integrations import SettlementAdjustment, SettlementEntry
from app.models.orders import OrderStatus, PaymentMethod, PaymentStatus
from app.services import refunds as refund_service
from app.services.refunds import (
    REFUND_REASON_CANCELLED,
    dispatch_refund,
    ensure_refund_request,
)
from app.services.settlements import (
    SETTLEMENT_PENDING,
    SETTLEMENT_SETTLED,
    SETTLEMENT_VOIDED,
    ensure_settlement_entry,
    settlement_is_eligible,
    void_settlement_for_refund,
)
from tests.factories import make_order, session


class _Provider:
    def __init__(self, status="processed"):
        self.calls = 0
        self._status = status

    def __call__(self, **kwargs):
        self.calls += 1
        return {"id": f"rfnd_{uuid4().hex[:12]}", "status": self._status}


def _entry_for(db, order) -> SettlementEntry | None:
    return db.query(SettlementEntry).filter(SettlementEntry.order_id == order.id).one_or_none()


def test_paid_order_creates_pending_settlement() -> None:
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()

        entry = ensure_settlement_entry(db, order)
        db.commit()

        assert entry is not None
        assert entry.status == SETTLEMENT_PENDING
        assert entry.gross_amount == order.total
        assert entry.merchant_amount == order.subtotal


def test_refund_success_voids_the_pending_settlement(monkeypatch) -> None:
    monkeypatch.setattr(refund_service, "razorpay_enabled", lambda: True)
    monkeypatch.setattr(refund_service, "create_razorpay_refund", _Provider())

    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        ensure_settlement_entry(db, order)
        db.commit()

        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        dispatch_refund(db, refund.id)

        db.refresh(order)
        entry = _entry_for(db, order)
        assert order.payment_status == PaymentStatus.REFUNDED
        assert entry is not None
        assert entry.status == SETTLEMENT_VOIDED
        assert entry.voided_at is not None
        assert entry.void_reason == "order_refunded"


def test_voiding_is_idempotent() -> None:
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        ensure_settlement_entry(db, order)
        db.commit()

        for _ in range(3):
            void_settlement_for_refund(db, order)
            db.commit()

        entry = _entry_for(db, order)
        assert entry.status == SETTLEMENT_VOIDED
        assert (
            db.query(SettlementAdjustment)
            .filter(SettlementAdjustment.order_id == order.id)
            .count()
            == 0
        )


def test_already_settled_entry_produces_an_auditable_reversal() -> None:
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        entry = ensure_settlement_entry(db, order)
        # Money already moved to the merchant.
        entry.status = SETTLEMENT_SETTLED
        db.commit()

        void_settlement_for_refund(db, order)
        db.commit()

        db.refresh(entry)
        # History is annotated, never rewritten.
        assert entry.status == SETTLEMENT_SETTLED
        adjustments = (
            db.query(SettlementAdjustment)
            .filter(SettlementAdjustment.order_id == order.id)
            .all()
        )
        assert len(adjustments) == 1
        assert adjustments[0].amount == -Decimal(order.subtotal)
        assert adjustments[0].status == "owed"


def test_reversal_of_settled_entry_is_idempotent() -> None:
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        entry = ensure_settlement_entry(db, order)
        entry.status = SETTLEMENT_SETTLED
        db.commit()

        for _ in range(4):
            void_settlement_for_refund(db, order)
            db.commit()

        assert (
            db.query(SettlementAdjustment)
            .filter(SettlementAdjustment.order_id == order.id)
            .count()
            == 1
        )


def test_refunded_order_can_never_be_newly_settled() -> None:
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()

        assert settlement_is_eligible(db, order) is False
        assert ensure_settlement_entry(db, order) is None
        assert _entry_for(db, order) is None


def test_cancelled_order_is_not_settleable() -> None:
    with session() as db:
        order = make_order(
            db,
            status=OrderStatus.CANCELLED,
            payment_status=PaymentStatus.PAID,
            with_paid_attempt=False,
        )
        db.commit()
        assert settlement_is_eligible(db, order) is False
        assert ensure_settlement_entry(db, order) is None


def test_unpaid_order_is_not_settleable() -> None:
    with session() as db:
        order = make_order(
            db,
            payment_status=PaymentStatus.PENDING,
            with_paid_attempt=False,
        )
        db.commit()
        assert settlement_is_eligible(db, order) is False
        assert ensure_settlement_entry(db, order) is None


def test_cod_order_settles_normally() -> None:
    """COD money reaches the merchant the same way; only the source differs."""
    with session() as db:
        order = make_order(
            db,
            payment_method=PaymentMethod.COD,
            payment_status=PaymentStatus.PAID,
            with_paid_attempt=False,
        )
        db.commit()
        entry = ensure_settlement_entry(db, order)
        db.commit()
        assert entry is not None
        assert entry.payment_method == "cod"
        assert entry.status == SETTLEMENT_PENDING


def test_settlement_creation_is_idempotent() -> None:
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        first = ensure_settlement_entry(db, order)
        db.commit()
        second = ensure_settlement_entry(db, order)
        db.commit()
        assert first.id == second.id
        assert (
            db.query(SettlementEntry).filter(SettlementEntry.order_id == order.id).count() == 1
        )


def test_void_without_any_settlement_is_a_no_op() -> None:
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        void_settlement_for_refund(db, order)
        db.commit()
        assert _entry_for(db, order) is None
