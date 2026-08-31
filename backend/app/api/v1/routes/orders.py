import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.commerce import Merchant, MerchantStatus, Store, StoreProduct
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
    DeliverySummaryRead,
    OrderDetailRead,
    OrderItemRead,
    OrderRead,
    OrderStatusUpdate,
)
from app.services.notifications import enqueue_notification
from app.services.pricing import order_total, resolve_delivery_fee
from app.services.order_transitions import (
    can_transition_delivery,
    can_transition_order,
    transition_delivery,
    transition_order,
)
from app.services.refunds import REFUND_REASON_CANCELLED, ensure_refund_request
from app.services.store_hours import store_is_open

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


def _can_view_order(db: Session, order: Order, user: User) -> bool:
    if user.role == UserRole.ADMIN or order.user_id == user.id:
        return True
    if user.role == UserRole.MERCHANT:
        merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
        store = db.get(Store, order.store_id)
        return bool(merchant and store and store.merchant_id == merchant.id)
    return False


def _order_detail(db: Session, order: Order) -> OrderDetailRead:
    store = db.get(Store, order.store_id)
    address = db.get(Address, order.address_id)
    if store is None:
        raise HTTPException(status_code=409, detail="Order references are incomplete")
    # The snapshot taken at checkout is the truth about where this order went.
    # The live address row is only a fallback for orders placed before
    # snapshots existed.
    snapshot = order.delivery_address or {}
    if not snapshot and address is None:
        raise HTTPException(status_code=409, detail="Order references are incomplete")

    def field(name: str):
        if name in snapshot:
            return snapshot[name]
        return getattr(address, name, None) if address is not None else None
    items = db.scalars(
        select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id)
    ).all()
    delivery = db.scalar(select(Delivery).where(Delivery.order_id == order.id))
    base = OrderRead.model_validate(order).model_dump()
    return OrderDetailRead(
        **base,
        store_name=store.name,
        store_phone=store.phone,
        store_landmark=store.landmark,
        recipient_name=field("recipient_name"),
        recipient_phone=field("phone"),
        house_details=field("house_details"),
        customer_landmark=field("landmark") or "",
        customer_directions=field("directions"),
        items=[OrderItemRead.model_validate(item) for item in items],
        delivery=(
            DeliverySummaryRead(
                id=delivery.id,
                delivery_partner_id=delivery.delivery_partner_id,
                status=delivery.status,
                assigned_at=delivery.assigned_at,
                picked_up_at=delivery.picked_up_at,
                delivered_at=delivery.delivered_at,
            )
            if delivery
            else None
        ),
    )


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
    store = db.get(Store, listing.store_id)
    merchant = db.get(Merchant, store.merchant_id) if store else None
    if store is None or not store.is_active or merchant is None or merchant.status != MerchantStatus.APPROVED:
        raise HTTPException(status_code=409, detail="Store is currently unavailable")
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


@router.delete("/cart", response_model=CartRead)
def clear_cart(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cart = _get_or_create_cart(db, user.id)
    db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
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
    if address is None or address.user_id != user.id or address.archived_at is not None:
        raise HTTPException(status_code=404, detail="Address not found")
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    if cart is None or cart.store_id is None:
        raise HTTPException(status_code=400, detail="Cart is empty")
    items = db.scalars(select(CartItem).where(CartItem.cart_id == cart.id)).all()
    if not items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    store = db.get(Store, cart.store_id)
    merchant = db.get(Merchant, store.merchant_id) if store else None
    if store is None or not store.is_active or merchant is None or merchant.status != MerchantStatus.APPROVED:
        raise HTTPException(status_code=409, detail="Store is currently unavailable")
    if not store.delivery_enabled:
        raise HTTPException(status_code=409, detail="This store does not currently support delivery")
    if not store_is_open(store):
        raise HTTPException(status_code=409, detail=f"{store.name} is closed right now.")

    subtotal = Decimal("0.00")
    for item in items:
        listing = item.store_product
        if not listing.is_available or listing.stock_quantity < item.quantity:
            raise HTTPException(status_code=409, detail="Cart inventory changed; review your cart")
        subtotal += listing.price * item.quantity

    delivery_fee = resolve_delivery_fee(db, store)
    order = Order(
        order_number=f"GO{datetime.now(timezone.utc).strftime('%y%m%d%H%M%S%f')[-14:]}",
        user_id=user.id,
        store_id=cart.store_id,
        address_id=address.id,
        payment_method=payload.payment_method,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total=order_total(subtotal, delivery_fee),
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
    _notify_merchant(
        db,
        order,
        "merchant.order_received",
        "New order received",
        f"Order {order.order_number} is waiting for confirmation.",
    )

    db.commit()
    db.refresh(order)
    return order


@router.get("/orders/me", response_model=list[OrderRead])
def my_orders(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return db.scalars(
        select(Order)
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()


@router.get("/orders/{order_id}", response_model=OrderDetailRead)
def order_detail(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if not _can_view_order(db, order, user):
        raise HTTPException(status_code=403, detail="You cannot view this order")
    return _order_detail(db, order)


@router.post("/orders/{order_id}/cancel", response_model=OrderRead)
def cancel_my_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if not can_transition_order(order.status, OrderStatus.CANCELLED):
        raise HTTPException(status_code=409, detail="Only newly placed orders can be cancelled")
    _restore_cancelled_stock(db, order)
    transition_order(order, OrderStatus.CANCELLED)
    # Refund obligations are recorded, never asserted. Setting REFUNDED here
    # would claim money moved that no provider call has returned.
    ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
    _notify_customer(
        db,
        order,
        "order.cancelled",
        "Order cancelled",
        f"Order {order.order_number} was cancelled successfully.",
    )
    _notify_merchant(
        db,
        order,
        "merchant.order_cancelled",
        "Order cancelled by customer",
        f"Order {order.order_number} was cancelled before acceptance.",
    )
    db.commit()
    db.refresh(order)
    return order


@router.get("/merchant/orders", response_model=list[OrderRead])
def merchant_orders(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
):
    stmt = select(Order).order_by(Order.created_at.desc())
    if user.role != UserRole.ADMIN:
        merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
        if merchant is None:
            raise HTTPException(status_code=404, detail="Merchant profile not found")
        store_ids = select(Store.id).where(Store.merchant_id == merchant.id)
        stmt = stmt.where(Order.store_id.in_(store_ids))
    return db.scalars(stmt.offset(offset).limit(limit)).all()


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
        if merchant.status != MerchantStatus.APPROVED:
            raise HTTPException(status_code=403, detail="Merchant is not active")

    if not can_transition_order(order.status, payload.status):
        raise HTTPException(
            status_code=409,
            detail=f"Invalid transition from {order.status.value} to {payload.status.value}",
        )

    if payload.status == OrderStatus.CANCELLED:
        _restore_cancelled_stock(db, order)
        ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
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

    transition_order(order, payload.status)
    db.commit()
    db.refresh(order)
    return order


@router.get("/delivery/available", response_model=list[DeliveryRead])
def available_deliveries(
    limit: int = Query(default=50, ge=1, le=200),
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
        .limit(limit)
    )
    return db.scalars(stmt).all()


@router.get("/delivery/me", response_model=list[DeliveryRead])
def my_deliveries(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.DELIVERY, UserRole.ADMIN)),
):
    stmt = select(Delivery).order_by(Delivery.updated_at.desc()).limit(limit)
    if user.role != UserRole.ADMIN:
        stmt = stmt.where(Delivery.delivery_partner_id == user.id)
    return db.scalars(stmt).all()


@router.post("/delivery/{delivery_id}/claim", response_model=DeliveryRead)
def claim_delivery(
    delivery_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.DELIVERY)),
):
    # Lock the rider before the delivery. Automatic dispatch locks the rider's
    # user row (spatial.nearest_eligible_rider, FOR UPDATE OF u), so taking the
    # same lock here puts self-claim and auto-assign in one ordering instead of
    # contending on different rows — which is how a rider ended up with two
    # active deliveries at once.
    rider = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if rider is None:
        raise HTTPException(status_code=404, detail="Delivery partner not found")

    delivery = db.scalar(select(Delivery).where(Delivery.id == delivery_id).with_for_update())
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    order = db.scalar(select(Order).where(Order.id == delivery.order_id).with_for_update())
    if (
        order is None
        or order.status != OrderStatus.READY
        or not can_transition_delivery(delivery.status, DeliveryStatus.ASSIGNED)
    ):
        raise HTTPException(status_code=409, detail="Delivery is not available")

    # One active delivery per rider. Every other path enforced this; the claim
    # endpoint never checked, so the rule was only as strong as the UI hiding
    # the button.
    active_delivery = db.scalar(
        select(Delivery.id)
        .where(
            Delivery.delivery_partner_id == rider.id,
            Delivery.status.in_((DeliveryStatus.ASSIGNED, DeliveryStatus.PICKED_UP)),
            Delivery.id != delivery.id,
        )
        .limit(1)
    )
    if active_delivery is not None:
        raise HTTPException(
            status_code=409, detail="Finish your current delivery before claiming another"
        )

    delivery.delivery_partner_id = user.id
    transition_delivery(delivery, DeliveryStatus.ASSIGNED)
    delivery.assigned_at = datetime.now(timezone.utc)
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
    # Pickup and release only. Completion and failure are deliberately absent:
    # completing a delivery requires verified proof (and a recorded cash
    # collection for COD), which lives in POST /delivery/{id}/complete, and
    # failure requires a reason, which lives in POST /delivery/{id}/fail.
    # DeliveryStatusUpdate rejects those two statuses at the schema layer; this
    # handler now has no branch that could act on them even if that changed.
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
    if not can_transition_delivery(delivery.status, payload.status):
        raise HTTPException(
            status_code=409,
            detail=f"Invalid delivery transition from {delivery.status.value} to {payload.status.value}",
        )

    order = db.scalar(select(Order).where(Order.id == delivery.order_id).with_for_update())
    if order is None:
        raise HTTPException(status_code=409, detail="Delivery order is missing")

    if payload.status == DeliveryStatus.PICKED_UP:
        if not can_transition_order(order.status, OrderStatus.OUT_FOR_DELIVERY):
            raise HTTPException(
                status_code=409,
                detail=f"Order cannot be picked up from {order.status.value}",
            )
        delivery.picked_up_at = datetime.now(timezone.utc)
        transition_order(order, OrderStatus.OUT_FOR_DELIVERY)
        _notify_customer(
            db,
            order,
            "delivery.picked_up",
            "Order picked up",
            "Your order has been collected from the store and is on its way.",
        )
    elif payload.status == DeliveryStatus.UNASSIGNED:
        # A rider stepping off a job is an operations event: it has to release
        # ownership and tell the customer, exactly as the admin path does.
        # Leaving delivery_partner_id set produced a delivery that was in the
        # open pool while still carrying a rider.
        if order.status != OrderStatus.READY:
            raise HTTPException(
                status_code=409,
                detail="A delivery can only be released while the order is still ready for pickup",
            )
        delivery.delivery_partner_id = None
        delivery.assigned_at = None
        _notify_customer(
            db,
            order,
            "delivery.reassignment",
            "Delivery partner is being reassigned",
            f"We are assigning another delivery partner to order {order.order_number}.",
        )

    transition_delivery(delivery, payload.status)
    db.commit()
    db.refresh(delivery)
    return delivery
