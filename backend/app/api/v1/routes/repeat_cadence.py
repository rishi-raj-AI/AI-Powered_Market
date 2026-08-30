from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
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


@router.get("/me/repeat-purchase-cadence")
def repeat_purchase_cadence(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(
        select(OrderItem.product_id, OrderItem.product_name, Order.created_at)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.user_id == user.id, Order.status == OrderStatus.DELIVERED)
        .order_by(OrderItem.product_id, Order.created_at)
    ).all()

    history: dict[object, list[tuple[str, datetime]]] = defaultdict(list)
    for product_id, product_name, created_at in rows:
        history[product_id].append((product_name, created_at))

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
        last_at = purchases[-1][1]
        days_since = max(0.0, (now - last_at).total_seconds() / 86400.0)
        due_ratio = days_since / max(cadence_days, 1.0)
        items.append({
            "product_id": str(product_id),
            "product_name": purchases[-1][0],
            "purchase_count": len(purchases),
            "cadence_days": round(cadence_days, 1),
            "days_since_last_purchase": round(days_since, 1),
            "due": due_ratio >= 0.85,
            "urgency_score": round(min(due_ratio, 2.0), 3),
        })

    items.sort(key=lambda item: (-item["urgency_score"], -item["purchase_count"], item["product_name"].casefold()))
    return {"items": items[:30]}
