"""Conservative, opt-in expiration of unpaid UPI stock reservations.

Provider reconciliation happens *before* cancellation. A provider error,
authorized payment, mismatched capture or multiple captures blocks expiry for
manual review rather than risking lost money. A late capture after cancellation
is handled by the existing orphaned-capture refund obligation.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.api.v1.routes.payment_hardening import _apply_paid, _notify_payment_captured
from app.models.integrations import PaymentAttempt
from app.models.orders import Order, OrderStatus, PaymentMethod, PaymentStatus
from app.services.audit import annotate_order_transition
from app.services.notifications import enqueue_notification
from app.services.order_transitions import transition_order
from app.services.payments import (
    PaymentProviderError,
    PaymentProviderUnavailable,
    amount_to_subunits,
    list_razorpay_order_payments,
)
from app.services.stock import restore_order_stock_once

logger = logging.getLogger(__name__)


def _utc_datetime(value: datetime) -> datetime:
    """Normalize legacy naive UTC timestamps before comparing cutoffs."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

_PAYMENT_ID_RE = re.compile(r"pay_[A-Za-z0-9_]+\Z", re.ASCII)
_ORDER_ID_RE = re.compile(r"order_[A-Za-z0-9_]+\Z", re.ASCII)


def expire_unpaid_orders(
    db: Session, *, limit: int = 25, age_minutes: int = 15,
) -> dict[str, int]:
    """Process eligible orders under order-first row locks.

    Must only be enabled after sandbox validation and operational approval.
    Does not call the refund provider; late captures create a durable refund
    obligation through the existing payment webhook path.
    """
    if limit < 1 or age_minutes < 1:
        raise ValueError("Expiration limit and age must be positive")
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=age_minutes)
    # Keyset pagination avoids starving later orders behind deferred legacy rows.
    # Keep each query and the overall invocation bounded.
    batch_size = min(max(limit * 10, 25), 500)
    scan_budget = min(max(limit * 100, 500), 5000)
    result = {"considered": 0, "expired": 0, "captured": 0, "deferred": 0}

    cursor = None
    while result["considered"] < scan_budget and result["expired"] + result["captured"] < limit:
        filters = [
            Order.payment_method == PaymentMethod.UPI,
            Order.payment_status.in_((PaymentStatus.PENDING, PaymentStatus.FAILED)),
            Order.status == OrderStatus.PLACED,
            Order.created_at < cutoff,
        ]
        if cursor is not None:
            filters.append(tuple_(Order.created_at, Order.id) > cursor)
        candidates = db.execute(
            select(Order.id, Order.created_at)
            .where(*filters)
            .order_by(Order.created_at, Order.id)
            .limit(min(batch_size, scan_budget - result["considered"]))
        ).all()
        if not candidates:
            break
        for order_id, created_at in candidates:
            if result["expired"] + result["captured"] >= limit:
                break
            cursor = (created_at, order_id)
            result["considered"] += 1
            try:
                order = db.scalar(
                    select(Order).where(Order.id == order_id).with_for_update(skip_locked=True)
                )
                if (
                    order is None or order.status != OrderStatus.PLACED
                    or order.payment_method != PaymentMethod.UPI
                    or order.payment_status not in (PaymentStatus.PENDING, PaymentStatus.FAILED)
                    or _utc_datetime(order.created_at) >= cutoff
                ):
                    db.rollback()
                    continue

                # A reservation already marked as stock-restored is inconsistent
                # with a still-placed unpaid order. Do not issue another stock
                # mutation or silently mark it paid; require operator review.
                if order.stock_restored_at is not None:
                    logger.warning(
                        "UPI expiry deferred for order_id=%s: stock already restored",
                        order.id,
                    )
                    db.rollback()
                    result["deferred"] += 1
                    continue

                # Corrupt zero/negative totals are not valid payment obligations.
                # Never infer nonpayment or reconcile a capture against them.
                if order.total is None or order.total <= 0:
                    logger.warning("UPI expiry deferred for order_id=%s: invalid total", order.id)
                    db.rollback()
                    result["deferred"] += 1
                    continue

                # Inspect every attempt, not just Razorpay attempts: an unknown
                # provider or locally recorded capture must block stock release.
                # Otherwise a stale order-level PENDING flag can conceal money.
                attempts = db.scalars(
                    select(PaymentAttempt)
                    .where(PaymentAttempt.order_id == order.id)
                    .order_by(PaymentAttempt.id)
                    .with_for_update()
                ).all()
                if not attempts:
                    # Legacy or inconsistent UPI orders without a recorded provider
                    # intent cannot be proven unpaid. Defer stock recovery until an
                    # operator reconciles the missing payment history.
                    logger.warning("UPI expiry deferred for order_id=%s: no payment attempts", order.id)
                    db.rollback()
                    result["deferred"] += 1
                    continue

                # A retry creates a fresh provider payment window even when the
                # commercial order is old. Never expire its reservation using only
                # the original order creation time: the provider may still accept
                # payment for a recently issued Razorpay intent.
                if any(
                    attempt.created_at is None
                    or _utc_datetime(attempt.created_at) >= cutoff
                    for attempt in attempts
                ):
                    logger.info("UPI expiry deferred for order_id=%s: recent payment attempt", order.id)
                    db.rollback()
                    result["deferred"] += 1
                    continue

                captured: list[tuple[PaymentAttempt, str]] = []
                seen_provider_payment_ids: set[str] = set()
                seen_provider_order_ids: set[str] = set()
                uncertain = False
                for attempt in attempts:
                    if attempt.provider != "razorpay":
                        uncertain = True
                        continue
                    if attempt.currency != "INR" or attempt.amount != order.total:
                        # A mismatched intent is not safe evidence that the
                        # commercial order was never charged.
                        uncertain = True
                    if attempt.status not in {"created", "attempted", "failed"} or attempt.provider_payment_id:
                        # Paid, authorized, processing, refunded, or unknown local
                        # states contradict a terminal unpaid reservation. Even an
                        # empty provider history cannot prove these safe to expire.
                        uncertain = True
                    if (
                        not isinstance(attempt.provider_order_id, str)
                        or not attempt.provider_order_id.strip()
                        or not _ORDER_ID_RE.fullmatch(attempt.provider_order_id)
                    ):
                        # A legacy attempt without a usable provider order ID
                        # cannot be reconciled with Razorpay. Local failed/created
                        # status is not authoritative evidence of nonpayment.
                        # Never restore reserved stock on this basis.
                        uncertain = True
                        continue
                    if attempt.provider_order_id in seen_provider_order_ids:
                        # A retry must have its own provider order identity. Reused
                        # intents are ambiguous even if provider history is empty;
                        # never treat duplicated local records as proof of nonpayment.
                        uncertain = True
                        continue
                    seen_provider_order_ids.add(attempt.provider_order_id)
                    # A provider intent shared with another commercial order is
                    # not exclusive evidence for this reservation. Even an empty
                    # provider history must not automatically release its stock.
                    other_order_id = db.scalar(
                        select(PaymentAttempt.order_id)
                        .where(
                            PaymentAttempt.provider == "razorpay",
                            PaymentAttempt.provider_order_id == attempt.provider_order_id,
                            PaymentAttempt.order_id != order.id,
                        )
                        .limit(1)
                    )
                    if other_order_id is not None:
                        uncertain = True
                        continue
                    payments = list_razorpay_order_payments(
                        provider_order_id=attempt.provider_order_id,
                    )
                    for payment in payments:
                        provider_status = payment.get("status")
                        payment_id = payment.get("id")
                        if isinstance(payment_id, str) and _PAYMENT_ID_RE.fullmatch(payment_id):
                            # Duplicate identities (including across retry orders) are
                            # ambiguous even if one record says captured and another
                            # says failed. Never auto-confirm or release stock.
                            if payment_id in seen_provider_payment_ids:
                                uncertain = True
                            seen_provider_payment_ids.add(payment_id)
                        if (
                            payment.get("order_id") != attempt.provider_order_id
                            or not isinstance(payment.get("id"), str)
                            or not _PAYMENT_ID_RE.fullmatch(payment["id"])
                        ):
                            uncertain = True
                            continue
                        if provider_status == "failed":
                            # A terminal failure with mismatched/missing money
                            # fields is malformed provider history, not reliable
                            # evidence that the order was never charged.
                            if (
                                type(payment.get("amount")) is not int
                                or payment["amount"] != amount_to_subunits(order.total)
                                or payment.get("currency") != attempt.currency
                            ):
                                uncertain = True
                            continue
                        if provider_status != "captured":
                            # Created, authorized, refunded, unrecognised or
                            # missing statuses are not proof of nonpayment.
                            uncertain = True
                            continue
                        if (
                            type(payment.get("amount")) is not int
                            or payment["amount"] != amount_to_subunits(order.total)
                            or payment.get("currency") != attempt.currency
                        ):
                            uncertain = True
                            continue
                        captured.append((attempt, payment["id"]))

                # Provider payment identities must also belong exclusively to this
                # commercial order. A legacy/corrupt row can associate a capture
                # with another order even when the provider order IDs differ.
                # Do not mark either order paid or release stock automatically.
                if captured:
                    for _attempt, payment_id in captured:
                        conflicting_order = db.scalar(
                            select(PaymentAttempt.order_id)
                            .where(
                                PaymentAttempt.provider == "razorpay",
                                PaymentAttempt.provider_payment_id == payment_id,
                                PaymentAttempt.order_id != order.id,
                            )
                            .limit(1)
                        )
                        if conflicting_order is not None:
                            uncertain = True
                            break

                # A second authorized payment may still capture. Do not release an
                # order with ambiguous provider state or multiple money movements.
                if len(captured) == 1 and not uncertain:
                    attempt, provider_payment_id = captured[0]
                    _apply_paid(db, attempt, order, provider_payment_id)
                    if (
                        order.payment_status != PaymentStatus.PAID
                        or attempt.status != "paid"
                        or attempt.provider_payment_id != provider_payment_id
                    ):
                        # A successful reconciliation must persist matching order and attempt evidence.
                        db.rollback()
                        result["deferred"] += 1
                        continue
                    _notify_payment_captured(db, order)
                    db.commit()
                    result["captured"] += 1
                elif captured or uncertain:
                    logger.warning("UPI expiry deferred for order_id=%s: provider state needs review", order.id)
                    db.rollback()
                    result["deferred"] += 1
                else:
                    restore_order_stock_once(db, order)
                    transition_order(order, OrderStatus.CANCELLED)
                    annotate_order_transition(
                        db, order, to_status=OrderStatus.CANCELLED.value,
                        reason="unpaid_upi_payment_window_expired",
                    )
                    enqueue_notification(
                        db, user_id=order.user_id,
                        event_type="order.payment_expired", title="Payment window expired",
                        body=f"Order {order.order_number} was cancelled because online payment was not completed.",
                        data={"order_id": str(order.id), "order_number": order.order_number},
                    )
                    db.commit()
                    result["expired"] += 1
            except (PaymentProviderError, PaymentProviderUnavailable):
                db.rollback()
                logger.warning("UPI expiry deferred for order_id=%s: provider unavailable", order_id)
                result["deferred"] += 1
            except Exception:
                db.rollback()
                logger.exception("UPI expiry failed for order_id=%s", order_id)
                result["deferred"] += 1
    return result
