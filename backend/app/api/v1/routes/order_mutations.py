import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.commerce import Merchant, MerchantStatus, Store, StoreProduct
from app.models.orders import Order, OrderItem, OrderStatus
from app.models.user import User, UserRole
from app.schemas.orders import OrderRead, OrderStatusUpdate
from app.services.notifications import enqueue_notification
from app.services.order_transitions import can_transition_order, transition_order
from app.services.refunds import (
    REFUND_REASON_CANCELLED,
    ensure_refund_request,
    try_dispatch_order_refund,
)

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


def _restore_stock_once(db: Session, order: Order) -> None:
    if order.stock_restored_at is not None:
        return

    items = db.scalars(
        select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.product_id)
    ).all()
    if not items:
        order.stock_restored_at = datetime.now(timezone.utc)
        return

    product_ids = sorted((item.product_id for item in items), key=str)
    listings = db.scalars(
        select(StoreProduct)
        .where(
            StoreProduct.store_id == order.store_id,
            StoreProduct.product_id.in_(product_ids),
        )
        .order_by(StoreProduct.product_id)
        .with_for_update()
    ).all()
    by_product = {listing.product_id: listing for listing in listings}

    for item in items:
        listing = by_product.get(item.product_id)
        if listing is None:
            raise HTTPException(status_code=409, detail="Order inventory reference is missing")
        listing.stock_quantity += item.quantity
        listing.is_available = True

    order.stock_restored_at = datetime.now(timezone.utc)


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

    _restore_stock_once(db, order)
    transition_order(order, OrderStatus.CANCELLED)
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

    if not can_transition_order(order.status, payload.status):
        raise HTTPException(
            status_code=409,
            detail=f"Invalid transition from {order.status.value} to {payload.status.value}",
        )

    store_refund = None
    if payload.status == OrderStatus.CANCELLED:
        _restore_stock_once(db, order)
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

    transition_order(order, payload.status)
    db.commit()
    if store_refund is not None:
        try_dispatch_order_refund(db, order.id)
    db.refresh(order)
    return order
