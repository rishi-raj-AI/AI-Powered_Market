import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.commerce import Merchant, MerchantStatus, Store
from app.models.orders import Delivery, DeliveryStatus, Order, OrderStatus

router = APIRouter(tags=["Commerce Intelligence"])


def reliability_score(*, delivered: int, cancelled: int, failed_deliveries: int, total: int) -> float:
    if total <= 0:
        return 0.5
    completion = delivered / total
    cancel_penalty = cancelled / total
    failure_penalty = failed_deliveries / total
    return round(
        max(
            0.0,
            min(
                1.0,
                completion - 0.45 * cancel_penalty - 0.35 * failure_penalty,
            ),
        ),
        3,
    )


@router.get("/stores/{store_id}/reliability")
def merchant_reliability(store_id: uuid.UUID, db: Session = Depends(get_db)):
    store = db.get(Store, store_id)
    merchant = db.get(Merchant, store.merchant_id) if store else None
    if store is None or not store.is_active or merchant is None or merchant.status != MerchantStatus.APPROVED:
        raise HTTPException(status_code=404, detail="Store not found")

    terminal_states = [OrderStatus.DELIVERED, OrderStatus.CANCELLED]
    counts = dict(
        db.execute(
            select(Order.status, func.count(Order.id))
            .where(Order.store_id == store_id, Order.status.in_(terminal_states))
            .group_by(Order.status)
        ).all()
    )
    delivered = int(counts.get(OrderStatus.DELIVERED, 0))
    cancelled = int(counts.get(OrderStatus.CANCELLED, 0))
    terminal_total = delivered + cancelled
    failed_deliveries = int(
        db.scalar(
            select(func.count(Delivery.id))
            .join(Order, Order.id == Delivery.order_id)
            .where(
                Order.store_id == store_id,
                Delivery.status == DeliveryStatus.FAILED,
                Order.status.in_(terminal_states),
            )
        )
        or 0
    )
    score = reliability_score(
        delivered=delivered,
        cancelled=cancelled,
        failed_deliveries=failed_deliveries,
        total=terminal_total,
    )
    if terminal_total < 5:
        confidence = "low"
    elif terminal_total < 25:
        confidence = "medium"
    else:
        confidence = "high"
    return {
        "store_id": str(store_id),
        "score": score,
        "confidence": confidence,
        "total_orders": terminal_total,
        "terminal_orders": terminal_total,
        "delivered_orders": delivered,
        "cancelled_orders": cancelled,
        "failed_deliveries": failed_deliveries,
        "basis": "terminal_operational_history",
    }
