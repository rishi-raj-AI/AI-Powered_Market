import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.commerce import Merchant, MerchantStatus, Store
from app.models.orders import Order, OrderStatus
from app.models.user import User, UserRole
from app.schemas.orders import OrderRead, OrderStatusUpdate
from app.services.audit import record_order_transition
from app.services.notifications import enqueue_notification
from app.services.order_transitions import (
    MERCHANT_ASSIGNABLE_STATUSES,
    can_transition_order,
    transition_order,
)
from app.services.refunds import (
    REFUND_REASON_CANCELLED,
    ensure_refund_request,
    try_dispatch_order_refund,
)
from app.services.stock import restore_order_stock_once

router = APIRouter(tags=["Order Mutations"])


def _notify_customer(db: Session, order: Order, event_type: str, title: str, body: str) -> None:
    enqueue_notification(
        db,
        user_id=order.user_id,
        event_type=event_type,
        title=title,
        body=body,
        data={"order_id": str(order.id), "order_number": order.order_number},
    )


def _notify_merchant(db: Session, order: Order, event_type: str, title: str, body: str) -> None:
    store = db.get(Store, order.store_id)
    merchant = db.get(Merchant, store.merchant_id) if store else None
    if merchant:
        enqueue_notification(
            db,
            user_id=merchant.owner_user_id,
            event_type=event_type,
            title=title,
            body=body,
            data={"order_id": str(order.id), "order_number": order.order_number},
        )


@router.post("/orders/{order_id}/cancel", response_model=OrderRead)
def cancel_my_order_safely(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if not can_transition_order(order.status, OrderStatus.CANCELLED):
        raise HTTPException(status_code=409, detail="Only newly placed orders can be cancelled")

    restore_order_stock_once(db, order)
    previous_status = order.status.value
    transition_order(order, OrderStatus.CANCELLED)
    record_order_transition(
        db,
        order,
        from_status=previous_status,
        to_status=OrderStatus.CANCELLED.value,
        actor_user_id=user.id,
        reason="customer_cancelled",
    )
    refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)

    _notify_customer(
        db,
        order,
        "order.cancelled",
        "Order cancelled",
        (
            f"Order {order.order_number} was cancelled. Your refund of ₹{order.total} has been "
            "requested and will reach your original payment method shortly."
            if refund is not None
            else f"Order {order.order_number} was cancelled successfully."
        ),
    )
    _notify_merchant(
        db,
        order,
        "merchant.order_cancelled",
        "Order cancelled by customer",
        f"Order {order.order_number} was cancelled before acceptance.",
    )
    db.commit()
    if refund is not None:
        try_dispatch_order_refund(db, order.id)
    db.refresh(order)
    return order


@router.patch("/merchant/orders/{order_id}/status", response_model=OrderRead)
def update_order_status_safely(
    order_id: uuid.UUID,
    payload: OrderStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
):
    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    if user.role != UserRole.ADMIN:
        merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
        store = db.get(Store, order.store_id)
        if merchant is None or store is None or store.merchant_id != merchant.id:
            raise HTTPException(status_code=403, detail="Order does not belong to your store")
        if merchant.status != MerchantStatus.APPROVED:
            raise HTTPException(status_code=403, detail="Merchant is not active")

    if payload.status not in MERCHANT_ASSIGNABLE_STATUSES:
        # RETURNED and DELIVERED carry financial consequences and are owned by
        # the delivery/operations flows, not the merchant order screen.
        raise HTTPException(
            status_code=403,
            detail=f"{payload.status.value} is not a merchant-assignable order status",
        )
    if not can_transition_order(order.status, payload.status):
        raise HTTPException(
            status_code=409,
            detail=f"Invalid transition from {order.status.value} to {payload.status.value}",
        )

    store_refund = None
    if payload.status == OrderStatus.CANCELLED:
        restore_order_stock_once(db, order)
        store_refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        _notify_customer(
            db,
            order,
            "order.cancelled",
            "Order cancelled",
            (
                f"Order {order.order_number} was cancelled by the store. Your refund of "
                f"₹{order.total} has been requested."
                if store_refund is not None
                else f"Order {order.order_number} was cancelled by the store."
            ),
        )
    elif payload.status == OrderStatus.ACCEPTED:
        _notify_customer(db, order, "order.accepted", "Order accepted", "The store accepted your order.")
    elif payload.status == OrderStatus.PREPARING:
        _notify_customer(db, order, "order.preparing", "Preparing your order", "The store is preparing your items.")
    elif payload.status == OrderStatus.READY:
        _notify_customer(
            db,
            order,
            "order.ready",
            "Order ready",
            "Your order is ready for pickup by a delivery partner.",
        )

    previous_status = order.status.value
    transition_order(order, payload.status)
    record_order_transition(
        db,
        order,
        from_status=previous_status,
        to_status=payload.status.value,
        actor_user_id=user.id,
        reason="merchant_status_update",
    )
    db.commit()
    if store_refund is not None:
        try_dispatch_order_refund(db, order.id)
    db.refresh(order)
    return order
