import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.orders import Delivery, DeliveryStatus, Order, OrderStatus, PaymentMethod, PaymentStatus
from app.models.user import User
from app.services.order_transitions import can_transition_order

router = APIRouter(tags=["Orders & Checkout"])


def _recovery_actions(order: Order, delivery: Delivery | None, now: datetime) -> list[dict]:
    actions: list[dict] = []
    if can_transition_order(order.status, OrderStatus.CANCELLED):
        actions.append({"code": "cancel_order", "label": "Cancel order", "priority": 10})

    if order.payment_method == PaymentMethod.UPI and order.payment_status in {PaymentStatus.PENDING, PaymentStatus.FAILED} and order.status != OrderStatus.CANCELLED:
        actions.append({"code": "retry_payment", "label": "Retry payment", "priority": 9})

    if delivery and delivery.status in {DeliveryStatus.ASSIGNED, DeliveryStatus.PICKED_UP}:
        actions.append({"code": "track_delivery", "label": "Track delivery", "priority": 8})

    age_minutes = max(0, int((now - order.updated_at).total_seconds() // 60)) if order.updated_at else 0
    if delivery and delivery.status == DeliveryStatus.FAILED:
        actions.append({"code": "contact_support", "label": "Get delivery help", "priority": 10})
    elif order.status in {OrderStatus.ACCEPTED, OrderStatus.PREPARING, OrderStatus.READY, OrderStatus.OUT_FOR_DELIVERY} and age_minutes >= 90:
        actions.append({"code": "contact_support", "label": "Order taking too long", "priority": 7})

    if order.status in {OrderStatus.CANCELLED, OrderStatus.DELIVERED}:
        actions.append({"code": "reorder_preview", "label": "Order these items again", "priority": 6})

    actions.sort(key=lambda item: (-item["priority"], item["code"]))
    return actions


@router.get("/orders/{order_id}/recovery")
def order_recovery(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = db.get(Order, order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    delivery = db.scalar(select(Delivery).where(Delivery.order_id == order.id))
    now = datetime.now(timezone.utc)
    actions = _recovery_actions(order, delivery, now)
    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "order_status": order.status.value,
        "payment_status": order.payment_status.value,
        "delivery_status": None if delivery is None else delivery.status.value,
        "actions": actions,
        "has_recovery_action": bool(actions),
    }
