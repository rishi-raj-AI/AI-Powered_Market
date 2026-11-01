"""Conservative, opt-in expiration of unpaid UPI stock reservations.

Provider reconciliation happens *before* cancellation. A provider error,
authorized payment, mismatched capture or multiple captures blocks expiry for
manual review rather than risking lost money. A late capture after cancellation
is handled by the existing orphaned-capture refund obligation.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
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
    candidates = db.scalars(
        select(Order.id)
        .where(
            Order.payment_method == PaymentMethod.UPI,
            Order.payment_status.in_((PaymentStatus.PENDING, PaymentStatus.FAILED)),
            Order.status == OrderStatus.PLACED,
            Order.created_at < cutoff,
        )
        .order_by(Order.created_at, Order.id)
        .limit(limit)
    ).all()
    result = {"considered": len(candidates), "expired": 0, "captured": 0, "deferred": 0}

    for order_id in candidates:
        try:
            order = db.scalar(
                select(Order).where(Order.id == order_id).with_for_update(skip_locked=True)
            )
            if (
                order is None or order.status != OrderStatus.PLACED
                or order.payment_method != PaymentMethod.UPI
                or order.payment_status not in (PaymentStatus.PENDING, PaymentStatus.FAILED)
                or order.created_at >= cutoff
            ):
                db.rollback()
                continue

            attempts = db.scalars(
                select(PaymentAttempt)
                .where(PaymentAttempt.order_id == order.id, PaymentAttempt.provider == "razorpay")
                .order_by(PaymentAttempt.id)
                .with_for_update()
            ).all()
            captured: list[tuple[PaymentAttempt, str]] = []
            uncertain = False
            for attempt in attempts:
                if not attempt.provider_order_id:
                    continue
                payments = list_razorpay_order_payments(
                    provider_order_id=attempt.provider_order_id,
                )
                for payment in payments:
                    provider_status = payment.get("status")
                    if provider_status == "authorized":
                        uncertain = True
                    if provider_status != "captured":
                        continue
                    if (
                        not isinstance(payment.get("id"), str)
                        or payment.get("order_id") != attempt.provider_order_id
                        or payment.get("amount") != amount_to_subunits(attempt.amount)
                        or payment.get("currency") != attempt.currency
                    ):
                        uncertain = True
                        continue
                    captured.append((attempt, payment["id"]))

            if len(captured) == 1:
                attempt, provider_payment_id = captured[0]
                _apply_paid(db, attempt, order, provider_payment_id)
                if order.payment_status == PaymentStatus.PAID:
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
