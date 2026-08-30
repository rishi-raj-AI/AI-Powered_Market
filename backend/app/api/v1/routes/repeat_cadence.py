from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.commerce import StoreProduct
from app.models.orders import Order, OrderItem, OrderStatus
from app.models.user import User

router = APIRouter(tags=["Commerce Intelligence"])


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _utc(value: datetime) -> datetime:
    """Normalize DB timestamps for safe arithmetic across DB/test drivers."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.get("/me/repeat-purchase-cadence")
def repeat_purchase_cadence(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(
        select(
            OrderItem.product_id,
            OrderItem.product_name,
            Order.created_at,
            Order.id,
            Order.store_id,
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.user_id == user.id, Order.status == OrderStatus.DELIVERED)
        .order_by(OrderItem.product_id, Order.created_at)
    ).all()

    history: dict[object, list[tuple[str, datetime, object, object]]] = defaultdict(list)
    for product_id, product_name, created_at, order_id, store_id in rows:
        history[product_id].append((product_name, _utc(created_at), order_id, store_id))

    now = datetime.now(timezone.utc)
    items = []
    for product_id, purchases in history.items():
        if len(purchases) < 2:
            continue
        intervals = [
            (purchases[index][1] - purchases[index - 1][1]).total_seconds() / 86400.0
            for index in range(1, len(purchases))
        ]
        cadence_days = _median(intervals)
        if cadence_days is None:
            continue
        last_name, last_at, last_order_id, last_store_id = purchases[-1]
        days_since = max(0.0, (now - last_at).total_seconds() / 86400.0)
        due_ratio = days_since / max(cadence_days, 1.0)
        listing = db.scalar(
            select(StoreProduct).where(
                StoreProduct.store_id == last_store_id,
                StoreProduct.product_id == product_id,
                StoreProduct.is_available.is_(True),
                StoreProduct.stock_quantity > 0,
            )
        )
        items.append({
            "product_id": str(product_id),
            "product_name": last_name,
            "purchase_count": len(purchases),
            "cadence_days": round(cadence_days, 1),
            "days_since_last_purchase": round(days_since, 1),
            "due": due_ratio >= 0.85,
            "urgency_score": round(min(due_ratio, 2.0), 3),
            "last_order_id": str(last_order_id),
            "last_store_id": str(last_store_id),
            "listing_id": str(listing.id) if listing is not None else None,
            "available_now": listing is not None,
        })

    items.sort(key=lambda item: (-item["urgency_score"], -item["purchase_count"], item["product_name"].casefold()))
    return {"items": items[:30]}
