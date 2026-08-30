import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.orders import (
    Delivery,
    DeliveryProof,
    DeliveryStatus,
    Order,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)
from app.models.user import User, UserRole
from app.schemas.orders import DeliveryRead
from app.services.notifications import enqueue_notification
from app.services.order_transitions import (
    can_transition_delivery,
    can_transition_order,
    transition_delivery,
    transition_order,
)
from app.services.settlements import ensure_settlement_entry

router = APIRouter(tags=["Delivery Operations"])


@router.post("/delivery/{delivery_id}/complete", response_model=DeliveryRead)
def complete_delivery_with_financials(
    delivery_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.DELIVERY, UserRole.ADMIN)),
):
    delivery = db.scalar(select(Delivery).where(Delivery.id == delivery_id).with_for_update())
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    order = db.scalar(select(Order).where(Order.id == delivery.order_id).with_for_update())
    if order is None:
        raise HTTPException(status_code=409, detail="Delivery order is missing")
    if user.role != UserRole.ADMIN and delivery.delivery_partner_id != user.id:
        raise HTTPException(status_code=403, detail="Delivery is not assigned to you")
    if not can_transition_delivery(delivery.status, DeliveryStatus.DELIVERED):
        raise HTTPException(status_code=409, detail=f"Delivery cannot be completed from {delivery.status.value}")
    if not can_transition_order(order.status, OrderStatus.DELIVERED):
        raise HTTPException(status_code=409, detail=f"Order cannot be delivered from {order.status.value}")
    proof = db.scalar(select(DeliveryProof).where(DeliveryProof.delivery_id == delivery.id).with_for_update())
    if proof is None or proof.verified_at is None:
        raise HTTPException(status_code=409, detail="Verified proof of delivery is required")

    transition_delivery(delivery, DeliveryStatus.DELIVERED)
    delivery.delivered_at = datetime.now(timezone.utc)
    transition_order(order, OrderStatus.DELIVERED)
    if order.payment_method == PaymentMethod.COD:
        order.payment_status = PaymentStatus.PAID
    if order.payment_status == PaymentStatus.PAID:
        ensure_settlement_entry(db, order)

    enqueue_notification(
        db,
        user_id=order.user_id,
        event_type="order.delivered",
        title="Order delivered",
        body=f"Order {order.order_number} has been delivered. Thank you for using GaonOne.",
        data={"order_id": str(order.id), "delivery_id": str(delivery.id)},
    )
    db.commit()
    db.refresh(delivery)
    return delivery
