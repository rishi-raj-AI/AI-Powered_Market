"""Refund obligations and their provider execution.

Design contract:

* A refund obligation is recorded transactionally with the commercial decision
  that creates it. It is never conditional on a provider call succeeding.
* ``PaymentStatus.REFUNDED`` is only ever written after the provider confirms
  the refund. Until then the order sits at ``REFUND_PENDING`` so nobody is told
  their money is back before it is.
* Provider execution is claim-then-call: the row is claimed and committed
  before any network I/O, so a crash mid-call leaves a recoverable record and
  never holds a database lock across a provider round trip.
* Repeated cancellation can never create a second refund: the obligation is
  keyed on the order and enforced by a unique constraint.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.integrations import PaymentAttempt, PaymentRefund
from app.models.orders import Order, PaymentMethod, PaymentStatus
from app.services.payments import (
    PaymentProviderError,
    PaymentProviderUnavailable,
    create_razorpay_refund,
    razorpay_enabled,
)

logger = logging.getLogger(__name__)

REFUND_REQUESTED = "requested"
REFUND_PROCESSING = "processing"
REFUND_SUCCEEDED = "succeeded"
REFUND_FAILED = "failed"

#: Statuses that still owe the customer money.
OPEN_REFUND_STATUSES = frozenset({REFUND_REQUESTED, REFUND_PROCESSING, REFUND_FAILED})
#: Statuses a dispatcher may pick up and send to the provider.
DISPATCHABLE_REFUND_STATUSES = frozenset({REFUND_REQUESTED, REFUND_FAILED})

MAX_REFUND_ATTEMPTS = 8

REFUND_REASON_CANCELLED = "order_cancelled"
REFUND_REASON_RETURNED = "delivery_returned"
REFUND_REASON_ORPHANED_CAPTURE = "capture_after_cancellation"


def refund_idempotency_key(order_id: uuid.UUID) -> str:
    """One full-order refund obligation per order, enforced by the database."""
    return f"order-refund:{order_id}"


def get_refund_for_order(db: Session, order_id: uuid.UUID) -> PaymentRefund | None:
    return db.scalar(
        select(PaymentRefund).where(PaymentRefund.idempotency_key == refund_idempotency_key(order_id))
    )


def _latest_captured_attempt(db: Session, order_id: uuid.UUID) -> PaymentAttempt | None:
    return db.scalar(
        select(PaymentAttempt)
        .where(
            PaymentAttempt.order_id == order_id,
            PaymentAttempt.status == "paid",
            PaymentAttempt.provider_payment_id.is_not(None),
        )
        .order_by(PaymentAttempt.updated_at.desc())
    )


def ensure_refund_request(db: Session, order: Order, *, reason: str) -> PaymentRefund | None:
    """Record that this order owes the customer money. Idempotent.

    Returns ``None`` when no refund is owed — cash-on-delivery orders never
    reach a payment provider, and an order whose money was never captured has
    nothing to give back.

    Adds to the caller's transaction without committing, so the obligation and
    the commercial state change land together or not at all.
    """
    if order.payment_method != PaymentMethod.UPI:
        return None
    if order.payment_status not in {PaymentStatus.PAID, PaymentStatus.REFUND_PENDING}:
        return None

    key = refund_idempotency_key(order.id)
    existing = db.scalar(select(PaymentRefund).where(PaymentRefund.idempotency_key == key).with_for_update())
    if existing is not None:
        return existing

    attempt = _latest_captured_attempt(db, order.id)
    refund = PaymentRefund(
        order_id=order.id,
        payment_attempt_id=attempt.id if attempt else None,
        provider="razorpay",
        provider_payment_id=attempt.provider_payment_id if attempt else None,
        amount=order.total,
        currency=attempt.currency if attempt else "INR",
        status=REFUND_REQUESTED,
        reason=reason,
        idempotency_key=key,
        requested_at=datetime.now(timezone.utc),
    )
    db.add(refund)
    try:
        db.flush()
    except IntegrityError:
        # A concurrent cancellation won the race; its obligation is the one
        # that counts and paying twice is the only unacceptable outcome.
        db.rollback()
        return db.scalar(select(PaymentRefund).where(PaymentRefund.idempotency_key == key))

    if order.payment_status == PaymentStatus.PAID:
        order.payment_status = PaymentStatus.REFUND_PENDING
    return refund


def _mark_succeeded(db: Session, refund: PaymentRefund, *, provider_status: str | None) -> None:
    refund.status = REFUND_SUCCEEDED
    refund.provider_status = provider_status
    refund.failure_reason = None
    refund.processed_at = datetime.now(timezone.utc)
    order = db.scalar(select(Order).where(Order.id == refund.order_id).with_for_update())
    if order is not None and order.payment_status != PaymentStatus.REFUNDED:
        order.payment_status = PaymentStatus.REFUNDED
        settle_refunded_order(db, order)


def settle_refunded_order(db: Session, order: Order) -> None:
    """Hook for downstream financial consequences of a confirmed refund.

    Settlement reversal is layered on top of this in its own change so the
    refund pipeline and the ledger stay independently testable.
    """
    return None


def _mark_failed(db: Session, refund: PaymentRefund, *, message: str) -> None:
    refund.status = REFUND_FAILED
    refund.failure_reason = message[:300]
    refund.failed_at = datetime.now(timezone.utc)


def apply_provider_refund_result(db: Session, refund: PaymentRefund, payload: dict) -> None:
    """Fold a provider refund object (API response or webhook) into our state."""
    provider_refund_id = str(payload.get("id") or "") or None
    provider_status = str(payload.get("status") or "") or None
    if provider_refund_id and not refund.provider_refund_id:
        refund.provider_refund_id = provider_refund_id
    refund.provider_status = provider_status

    if provider_status == "processed":
        _mark_succeeded(db, refund, provider_status=provider_status)
    elif provider_status == "failed":
        _mark_failed(db, refund, message="Razorpay reported the refund as failed")
    else:
        # 'pending' and anything unrecognised: the provider accepted the refund
        # but has not settled it. Wait for the webhook rather than guessing.
        refund.status = REFUND_PROCESSING


def dispatch_refund(db: Session, refund_id: uuid.UUID) -> str:
    """Send one owed refund to the provider. Safe to call repeatedly.

    Returns the refund's status after the attempt.
    """
    refund = db.scalar(select(PaymentRefund).where(PaymentRefund.id == refund_id).with_for_update())
    if refund is None:
        return "missing"
    if refund.status not in DISPATCHABLE_REFUND_STATUSES:
        return refund.status
    if refund.attempt_count >= MAX_REFUND_ATTEMPTS:
        return refund.status
    if not refund.provider_payment_id:
        _mark_failed(
            db,
            refund,
            message="No captured provider payment id is recorded for this order; manual reconciliation required",
        )
        refund.attempt_count = MAX_REFUND_ATTEMPTS
        db.commit()
        return refund.status
    if not razorpay_enabled():
        _mark_failed(db, refund, message="Razorpay credentials are not configured")
        db.commit()
        return refund.status

    # Claim the row and release the lock before touching the network.
    refund.status = REFUND_PROCESSING
    refund.attempt_count += 1
    provider_payment_id = refund.provider_payment_id
    amount = Decimal(refund.amount)
    idempotency_key = refund.idempotency_key
    order_id = str(refund.order_id)
    db.commit()

    try:
        payload = create_razorpay_refund(
            provider_payment_id=provider_payment_id,
            amount=amount,
            idempotency_key=idempotency_key,
            notes={"gaonone_order_id": order_id},
        )
    except (PaymentProviderError, PaymentProviderUnavailable) as exc:
        locked = db.scalar(select(PaymentRefund).where(PaymentRefund.id == refund_id).with_for_update())
        if locked is not None:
            _mark_failed(db, locked, message=str(exc))
            logger.warning(
                "Refund dispatch failed refund_id=%s order_id=%s attempt=%s: %s",
                refund_id,
                order_id,
                locked.attempt_count,
                exc,
            )
        db.commit()
        return REFUND_FAILED

    locked = db.scalar(select(PaymentRefund).where(PaymentRefund.id == refund_id).with_for_update())
    if locked is None:
        return "missing"
    apply_provider_refund_result(db, locked, payload)
    status = locked.status
    logger.info(
        "Refund dispatched refund_id=%s order_id=%s provider_refund_id=%s status=%s",
        refund_id,
        order_id,
        locked.provider_refund_id,
        status,
    )
    db.commit()
    return status


def due_refund_ids(db: Session, *, limit: int = 50, order_id: uuid.UUID | None = None) -> list[uuid.UUID]:
    stmt = (
        select(PaymentRefund.id)
        .where(
            PaymentRefund.status.in_(tuple(DISPATCHABLE_REFUND_STATUSES)),
            PaymentRefund.attempt_count < MAX_REFUND_ATTEMPTS,
        )
        .order_by(PaymentRefund.requested_at)
        .limit(limit)
    )
    if order_id is not None:
        stmt = stmt.where(PaymentRefund.order_id == order_id)
    return list(db.scalars(stmt).all())


def dispatch_due_refunds(db: Session, *, limit: int = 50, order_id: uuid.UUID | None = None) -> dict[str, int]:
    """Drain owed refunds. Used by the worker and by admin-triggered retries."""
    outcome = {"considered": 0, "succeeded": 0, "processing": 0, "failed": 0}
    for refund_id in due_refund_ids(db, limit=limit, order_id=order_id):
        outcome["considered"] += 1
        status = dispatch_refund(db, refund_id)
        if status == REFUND_SUCCEEDED:
            outcome["succeeded"] += 1
        elif status == REFUND_PROCESSING:
            outcome["processing"] += 1
        elif status == REFUND_FAILED:
            outcome["failed"] += 1
    return outcome


def try_dispatch_order_refund(db: Session, order_id: uuid.UUID) -> None:
    """Best-effort immediate dispatch after a cancellation commits.

    Never raises: the durable obligation plus the worker are what guarantee the
    refund happens, so a provider hiccup must not turn a successful
    cancellation into an error for the customer.
    """
    try:
        dispatch_due_refunds(db, limit=1, order_id=order_id)
    except Exception:  # the obligation is already durable; never fail the cancellation
        db.rollback()
        logger.exception("Immediate refund dispatch failed for order_id=%s", order_id)
