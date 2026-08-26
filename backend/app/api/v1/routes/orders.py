import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.commerce import Merchant, Store, StoreProduct
from app.models.geography import Address
from app.models.orders import (
    Cart,
    CartItem,
    Delivery,
    DeliveryStatus,
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)
from app.models.user import User, UserRole
from app.schemas.orders import (
    CartItemUpsert,
    CartRead,
    CheckoutRequest,
    DeliveryRead,
    DeliveryStatusUpdate,
    OrderRead,
    OrderStatusUpdate,
)
from app.services.notifications import enqueue_notification

router = APIRouter(tags=["Orders & Delivery"])


def _get_or_create_cart(db: Session, user_id: uuid.UUID) -> Cart:
    cart = db.scalar(select(Cart).where(Cart.user_id == user_id))
    if cart is None:
        cart = Cart(user_id=user_id)
        db.add(cart)
        db.flush()
    return cart


def _cart_payload(db: Session, cart: Cart) -> CartRead:
    items = db.scalars(select(CartItem).where(CartItem.cart_id == cart.id)).all()
    subtotal = sum((item.store_product.price * item.quantity for item in items), Decimal("0.00"))
    return CartRead(id=cart.id, store_id=cart.store_id, items=items, subtotal=subtotal)


def _notify_customer(db: Session, order: Order, event_type: str, title: str, body: str) -> None:
    enqueue_notification(
        db,
        user_id=order.user_id,
        event_type=event_type,
        title=title,
        body=body,
        data={"order_id": str(order.id), "order_number": order.order_number},
    )


def _restore_cancelled_stock(db: Session, order: Order) -> None:
    items = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    for item in items:
        listing = db.scalar(
            select(StoreProduct).where(
                StoreProduct.store_id == order.store_id,
                StoreProduct.product_id == item.product_id,
            )
        )
        if listing:
            listing.stock_quantity += item.quantity
            listing.is_available = True


@router.get("/cart", response_model=CartRead)
def get_cart(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cart = _get_or_create_cart(db, user.id)
    db.commit()
    return _cart_payload(db, cart)


@router.post("/cart/items", response_model=CartRead)
def add_cart_item(
    payload: CartItemUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    listing = db.get(StoreProduct, payload.store_product_id)
    if listing is None or not listing.is_available or listing.stock_quantity < payload.quantity:
        raise HTTPException(status_code=400, detail="Product is unavailable or insufficient stock")
    cart = _get_or_create_cart(db, user.id)
    if cart.store_id and cart.store_id != listing.store_id:
        raise HTTPException(status_code=409, detail="Cart can contain products from only one store")
    cart.store_id = listing.store_id
    item = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.store_product_id == listing.id,
        )
    )
    if item:
        item.quantity = payload.quantity
    else:
        db.add(CartItem(cart_id=cart.id, store_product_id=listing.id, quantity=payload.quantity))
    db.commit()
    db.refresh(cart)
    return _cart_payload(db, cart)


@router.delete("/cart/items/{store_product_id}", response_model=CartRead)
def remove_cart_item(
    store_product_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cart = _get_or_create_cart(db, user.id)
    db.execute(
        delete(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.store_product_id == store_product_id,
        )
    )
    db.flush()
    remaining = db.scalar(select(CartItem.id).where(CartItem.cart_id == cart.id).limit(1))
    if remaining is None:
        cart.store_id = None
    db.commit()
    return _cart_payload(db, cart)


@router.post("/orders/checkout", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def checkout(
    payload: CheckoutRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    address = db.get(Address, payload.address_id)
    if address is None or address.user_id != user.id:
        raise HTTPException(status_code=404, detail="Address not found")
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    if cart is None or cart.store_id is None:
        raise HTTPException(status_code=400, detail="Cart is empty")
    items = db.scalars(select(CartItem).where(CartItem.cart_id == cart.id)).all()
    if not items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    store = db.get(Store, cart.store_id)
    if store is None or not store.is_active:
        raise HTTPException(status_code=409, detail="Store is currently unavailable")
    if payload.payment_method == PaymentMethod.COD and not store.delivery_enabled:
        raise HTTPException(status_code=409, detail="This store does not currently support delivery")

    subtotal = Decimal("0.00")
    for item in items:
        listing = item.store_product
        if not listing.is_available or listing.stock_quantity < item.quantity:
            raise HTTPException(status_code=409, detail="Cart inventory changed; review your cart")
        subtotal += listing.price * item.quantity

    delivery_fee = Decimal("20.00")
    order = Order(
        order_number=f"GO{datetime.now(timezone.utc).strftime('%y%m%d%H%M%S%f')[-14:]}",
        user_id=user.id,
        store_id=cart.store_id,
        address_id=address.id,
        payment_method=payload.payment_method,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total=subtotal + delivery_fee,
    )
    db.add(order)
    db.flush()

    for item in items:
        listing = item.store_product
        product = listing.product
        line_total = listing.price * item.quantity
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                unit=product.unit,
                unit_price=listing.price,
                quantity=item.quantity,
                line_total=line_total,
            )
        )
        listing.stock_quantity -= item.quantity
        if listing.stock_quantity == 0:
            listing.is_available = False

    db.add(Delivery(order_id=order.id))
    db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    cart.store_id = None

    _notify_customer(
        db,
        order,
        "order.placed",
        "Order placed",
        f"Your order {order.order_number} has been placed successfully.",
    )
    merchant = db.get(Merchant, store.merchant_id)
    if merchant:
        enqueue_notification(
            db,
            user_id=merchant.owner_user_id,
            event_type="merchant.order_received",
            title="New order received",
            body=f"Order {order.order_number} is waiting for confirmation.",
            data={"order_id": str(order.id), "order_number": order.order_number},
        )

    db.commit()
    db.refresh(order)
    return order


@router.get("/orders/me", response_model=list[OrderRead])
def my_orders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(
        select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())
    ).all()


@router.get("/merchant/orders", response_model=list[OrderRead])
def merchant_orders(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
):
    if user.role == UserRole.ADMIN:
        return db.scalars(select(Order).order_by(Order.created_at.desc())).all()
    merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
    if merchant is None:
        raise HTTPException(status_code=404, detail="Merchant profile not found")
    store_ids = select(Store.id).where(Store.merchant_id == merchant.id)
    return db.scalars(
        select(Order).where(Order.store_id.in_(store_ids)).order_by(Order.created_at.desc())
    ).all()


@router.patch("/merchant/orders/{order_id}/status", response_model=OrderRead)
def update_order_status(
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

    allowed = {
        OrderStatus.PLACED: {OrderStatus.ACCEPTED, OrderStatus.CANCELLED},
        OrderStatus.ACCEPTED: {OrderStatus.PREPARING, OrderStatus.CANCELLED},
        OrderStatus.PREPARING: {OrderStatus.READY},
    }
    if payload.status not in allowed.get(order.status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Invalid transition from {order.status.value} to {payload.status.value}",
        )

    if payload.status == OrderStatus.CANCELLED:
        _restore_cancelled_stock(db, order)
        _notify_customer(
            db,
            order,
            "order.cancelled",
            "Order cancelled",
            f"Order {order.order_number} was cancelled by the store.",
        )
    elif payload.status == OrderStatus.ACCEPTED:
        _notify_customer(db, order, "order.accepted", "Order accepted", "The store accepted your order.")
    elif payload.status == OrderStatus.PREPARING:
        _notify_customer(db, order, "order.preparing", "Preparing your order", "The store is preparing your items.")
    elif payload.status == OrderStatus.READY:
        _notify_customer(db, order, "order.ready", "Order ready", "Your order is ready for pickup by a delivery partner.")

    order.status = payload.status
    db.commit()
    db.refresh(order)
    return order


@router.get("/delivery/available", response_model=list[DeliveryRead])
def available_deliveries(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.DELIVERY, UserRole.ADMIN)),
):
    stmt = (
        select(Delivery)
        .join(Order, Delivery.order_id == Order.id)
        .where(
            Delivery.status == DeliveryStatus.UNASSIGNED,
            Order.status == OrderStatus.READY,
        )
    )
    return db.scalars(stmt).all()


@router.get("/delivery/me", response_model=list[DeliveryRead])
def my_deliveries(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.DELIVERY, UserRole.ADMIN)),
):
    stmt = (
        select(Delivery)
        .where(Delivery.delivery_partner_id == user.id)
        .order_by(Delivery.updated_at.desc())
    )
    return db.scalars(stmt).all()


@router.post("/delivery/{delivery_id}/claim", response_model=DeliveryRead)
def claim_delivery(
    delivery_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.DELIVERY)),
):
    delivery = db.scalar(select(Delivery).where(Delivery.id == delivery_id).with_for_update())
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    order = db.get(Order, delivery.order_id)
    if delivery.status != DeliveryStatus.UNASSIGNED or order is None or order.status != OrderStatus.READY:
        raise HTTPException(status_code=409, detail="Delivery is not available")

    delivery.delivery_partner_id = user.id
    delivery.status = DeliveryStatus.ASSIGNED
    delivery.assigned_at = datetime.now(timezone.utc)
    order.status = OrderStatus.OUT_FOR_DELIVERY
    _notify_customer(
        db,
        order,
        "delivery.assigned",
        "Delivery partner assigned",
        f"A delivery partner is on the way for order {order.order_number}.",
    )
    db.commit()
    db.refresh(delivery)
    return delivery


@router.patch("/delivery/{delivery_id}/status", response_model=DeliveryRead)
def update_delivery_status(
    delivery_id: uuid.UUID,
    payload: DeliveryStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.DELIVERY, UserRole.ADMIN)),
):
    delivery = db.scalar(select(Delivery).where(Delivery.id == delivery_id).with_for_update())
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if user.role != UserRole.ADMIN and delivery.delivery_partner_id != user.id:
        raise HTTPException(status_code=403, detail="Delivery is not assigned to you")

    allowed = {
        DeliveryStatus.ASSIGNED: {DeliveryStatus.PICKED_UP},
        DeliveryStatus.PICKED_UP: {DeliveryStatus.DELIVERED},
    }
    if payload.status not in allowed.get(delivery.status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Invalid delivery transition from {delivery.status.value} to {payload.status.value}",
        )

    order = db.get(Order, delivery.order_id)
    if payload.status == DeliveryStatus.PICKED_UP:
        delivery.picked_up_at = datetime.now(timezone.utc)
        if order:
            _notify_customer(
                db,
                order,
                "delivery.picked_up",
                "Order picked up",
                "Your order has been collected from the store and is on its way.",
            )
    elif payload.status == DeliveryStatus.DELIVERED:
        delivery.delivered_at = datetime.now(timezone.utc)
        if order:
            order.status = OrderStatus.DELIVERED
            if order.payment_method == PaymentMethod.COD:
                order.payment_status = PaymentStatus.PAID
            _notify_customer(
                db,
                order,
                "order.delivered",
                "Order delivered",
                f"Order {order.order_number} has been delivered. Thank you for using GaonOne.",
            )

    delivery.status = payload.status
    db.commit()
    db.refresh(delivery)
    return delivery
