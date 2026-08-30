"""The merchant settlement ledger.

Settlement eligibility is derived from authoritative order, payment and refund
state — never from the fact that a row already exists. The ledger is
append-and-annotate: rows are voided or corrected, never deleted, so the
financial history always explains itself.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.commerce import Store
from app.models.integrations import PaymentRefund, SettlementAdjustment, SettlementEntry
from app.models.orders import Order, OrderStatus, PaymentStatus

logger = logging.getLogger(__name__)

SETTLEMENT_PENDING = "pending"
SETTLEMENT_SETTLED = "settled"
SETTLEMENT_VOIDED = "voided"

#: A settlement in this state has not yet moved money to the merchant, so it
#: can simply be voided.
REVERSIBLE_SETTLEMENT_STATUSES = frozenset({SETTLEMENT_PENDING})

VOID_REASON_REFUNDED = "order_refunded"
VOID_REASON_RETURNED = "delivery_returned"


class SettlementNotEligible(ValueError):
    """The order's authoritative state does not entitle the merchant to money."""


def settlement_is_eligible(db: Session, order: Order) -> bool:
    """Recompute entitlement from authoritative state rather than trusting a row."""
    if order.payment_status != PaymentStatus.PAID:
        return False
    if order.status == OrderStatus.CANCELLED:
        return False
    # Any open or completed refund obligation means this money is not the
    # merchant's, whatever the payment status currently reads.
    refund = db.scalar(select(PaymentRefund).where(PaymentRefund.order_id == order.id))
    if refund is not None:
        return False
    return True


def ensure_settlement_entry(db: Session, order: Order) -> SettlementEntry | None:
    """Create merchant entitlement for a paid order. Idempotent.

    Returns ``None`` when the order's authoritative state does not entitle the
    merchant to anything — a late provider event for a refunded order is a
    normal occurrence, not an error worth failing a webhook over.
    """
    existing = db.scalar(
        select(SettlementEntry).where(SettlementEntry.order_id == order.id).with_for_update()
    )
    if existing is not None:
        return existing
    if not settlement_is_eligible(db, order):
        logger.info(
            "Settlement entry withheld order_id=%s payment_status=%s order_status=%s",
            order.id,
            order.payment_status.value,
            order.status.value,
        )
        return None
    store = db.get(Store, order.store_id)
    if store is None:
        raise ValueError("Settlement entry requires a valid store")
    entry = SettlementEntry(
        order_id=order.id,
        store_id=store.id,
        merchant_id=store.merchant_id,
        payment_method=order.payment_method.value,
        gross_amount=order.total,
        merchant_amount=order.subtotal,
        delivery_fee_amount=order.delivery_fee,
        status=SETTLEMENT_PENDING,
    )
    db.add(entry)
    db.flush()
    return entry


def void_settlement_for_refund(db: Session, order: Order, *, reason: str = VOID_REASON_REFUNDED) -> None:
    """Remove merchant entitlement for an order whose money went back. Idempotent.

    A pending entry is voided in place. An entry that was already settled is
    corrected with an explicit negative adjustment, because pretending money
    never moved would make the ledger lie.
    """
    entry = db.scalar(
        select(SettlementEntry).where(SettlementEntry.order_id == order.id).with_for_update()
    )
    if entry is None:
        return

    if entry.status == SETTLEMENT_VOIDED:
        return

    if entry.status in REVERSIBLE_SETTLEMENT_STATUSES:
        entry.status = SETTLEMENT_VOIDED
        entry.voided_at = datetime.now(timezone.utc)
        entry.void_reason = reason
        logger.info(
            "Settlement voided order_id=%s settlement_entry_id=%s reason=%s",
            order.id,
            entry.id,
            reason,
        )
        return

    # Already settled: record the correction as its own auditable fact.
    key = f"settlement-reversal:{entry.id}"
    existing = db.scalar(
        select(SettlementAdjustment).where(SettlementAdjustment.idempotency_key == key)
    )
    if existing is not None:
        return
    adjustment = SettlementAdjustment(
        settlement_entry_id=entry.id,
        order_id=order.id,
        merchant_id=entry.merchant_id,
        amount=-Decimal(entry.merchant_amount),
        reason=reason,
        status="owed",
        idempotency_key=key,
    )
    db.add(adjustment)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return
    logger.info(
        "Settlement reversal recorded order_id=%s settlement_entry_id=%s amount=%s reason=%s",
        order.id,
        entry.id,
        adjustment.amount,
        reason,
    )
