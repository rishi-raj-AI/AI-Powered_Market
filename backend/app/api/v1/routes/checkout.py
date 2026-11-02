import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.commerce import Merchant, MerchantStatus, Store, StoreProduct
from app.models.geography import Address
from app.models.orders import Cart, CartItem, Delivery, Order, OrderItem, PaymentMethod
from app.models.user import User
from app.schemas.orders import CheckoutQuoteRead, CheckoutRequest, OrderRead
from app.services.notifications import enqueue_notification
from app.services.pricing import order_total, resolve_delivery_fee
from app.services.delivery_serviceability import evaluate_delivery
from app.services.store_hours import describe_hours, store_is_open

router = APIRouter(tags=["Orders & Checkout"])


def _notify_customer(db: Session, order: Order) -> None:
    enqueue_notification(
        db,
        user_id=order.user_id,
        event_type="order.placed",
        title="Order placed",
        body=f"Your order {order.order_number} has been placed successfully.",
        data={"order_id": str(order.id), "order_number": order.order_number},
    )


def _notify_merchant(db: Session, order: Order, store: Store) -> None:
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


def _existing_idempotent_order(db: Session, user_id: uuid.UUID, key: str | None) -> Order | None:
    if not key:
        return None
    return db.scalar(
        select(Order).where(
            Order.user_id == user_id,
            Order.idempotency_key == key,
        )
    )


def _validate_idempotent_checkout_replay(order: Order, payload: CheckoutRequest) -> Order:
    """A retry may retrieve only the order created for the same checkout intent.

    The cart may already have been cleared, and the original address may now
    be archived; compare persisted order fields rather than current cart or
    address state. Never silently return a COD order for a UPI request (or
    another delivery address) using the same idempotency key.
    """
    if order.address_id != payload.address_id or order.payment_method != payload.payment_method:
        raise HTTPException(
            status_code=409,
            detail="Idempotency-Key was already used for a different checkout request",
        )
    return order


def _new_order_number() -> str:
    """Time-ordered and collision-resistant.

    The previous scheme was day/time plus microseconds against a unique column,
    so two orders in the same microsecond became an unhandled 500 during
    checkout. The random suffix removes that failure mode.
    """
    stamp = datetime.now(timezone.utc).strftime("%y%m%d%H%M%S")
    # 5 random bytes gives ~1.1e12 values per second, so even a burst of
    # thousands of orders in the same second collides with vanishing
    # probability. Total length 24, well inside the column's 32.
    return f"GO{stamp}{secrets.token_hex(5).upper()}"


def _address_snapshot(address: Address) -> dict:
    """Freeze where this order is going, so order history cannot drift."""
    return {
        key: value
        for key, value in {
            "recipient_name": address.recipient_name,
            "phone": address.phone,
            "house_details": address.house_details,
            "landmark": address.landmark,
            "directions": address.directions,
            "latitude": address.latitude,
            "longitude": address.longitude,
            "village_id": str(address.village_id),
        }.items()
        if value is not None
    }


@router.get("/cart/quote", response_model=CheckoutQuoteRead)
def cart_quote(
    address_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return a current, backend-authoritative checkout preview.

    This is intentionally read-only and does not reserve stock. The mutation
    endpoint repeats every check while holding inventory locks.
    """
    address = db.get(Address, address_id)
    if address is None or address.user_id != user.id or address.archived_at is not None:
        raise HTTPException(status_code=404, detail="Address not found")
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    if cart is None or cart.store_id is None:
        raise HTTPException(status_code=400, detail="Cart is empty")
    store = db.get(Store, cart.store_id)
    merchant = db.get(Merchant, store.merchant_id) if store else None
    if store is None or not store.is_active or merchant is None or merchant.status != MerchantStatus.APPROVED:
        raise HTTPException(status_code=409, detail="Store is currently unavailable")

    rows = db.execute(
        select(
            CartItem.quantity,
            StoreProduct.price,
            StoreProduct.stock_quantity,
            StoreProduct.is_available,
            StoreProduct.store_id,
        )
        .join(StoreProduct, StoreProduct.id == CartItem.store_product_id)
        .where(CartItem.cart_id == cart.id)
    ).all()
    if not rows:
        raise HTTPException(status_code=400, detail="Cart is empty")

    subtotal = Decimal("0.00")
    inventory_valid = True
    for row in rows:
        if row.store_id != store.id or not row.is_available or row.stock_quantity < row.quantity:
            inventory_valid = False
        subtotal += row.price * row.quantity

    delivery_decision = evaluate_delivery(db, store, address, merchant=merchant)
    serviceable = delivery_decision.serviceable
    open_now = store_is_open(store)
    blockers: list[str] = []
    if not inventory_valid:
        blockers.append("Cart inventory changed; review your cart")
    if not serviceable:
        blockers.append(delivery_decision.human_readable_message)
    if not open_now:
        blockers.append("Store is currently closed")
    delivery_fee = resolve_delivery_fee(db, store)
    return CheckoutQuoteRead(
        store_id=store.id,
        address_id=address.id,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total=order_total(subtotal, delivery_fee),
        serviceable=serviceable,
        serviceability_reason_code=delivery_decision.reason_code,
        inventory_valid=inventory_valid,
        store_open=open_now,
        checkout_ready=serviceable and inventory_valid and open_now,
        blockers=blockers,
    )


@router.post("/orders/checkout", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def safe_checkout(
    payload: CheckoutRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > 128:
            raise HTTPException(status_code=400, detail="Idempotency-Key must contain 1 to 128 characters")
        existing = _existing_idempotent_order(db, user.id, idempotency_key)
        if existing:
            return _validate_idempotent_checkout_replay(existing, payload)

    address = db.get(Address, payload.address_id)
    if address is None or address.user_id != user.id or address.archived_at is not None:
        raise HTTPException(status_code=404, detail="Address not found")

    cart = db.scalar(select(Cart).where(Cart.user_id == user.id).with_for_update())

    existing = _existing_idempotent_order(db, user.id, idempotency_key)
    if existing:
        return _validate_idempotent_checkout_replay(existing, payload)

    if cart is None or cart.store_id is None:
        raise HTTPException(status_code=400, detail="Cart is empty")

    items = db.scalars(
        select(CartItem)
        .where(CartItem.cart_id == cart.id)
        .order_by(CartItem.store_product_id)
    ).all()
    if not items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    store = db.get(Store, cart.store_id)
    merchant = db.get(Merchant, store.merchant_id) if store else None
    if store is None or not store.is_active or merchant is None or merchant.status != MerchantStatus.APPROVED:
        raise HTTPException(status_code=409, detail="Store is currently unavailable")
    delivery_decision = evaluate_delivery(db, store, address, merchant=merchant)
    if not delivery_decision.serviceable:
        raise HTTPException(status_code=409, detail=delivery_decision.human_readable_message)
    if not store_is_open(store):
        hours = describe_hours(store.opens_at, store.closes_at)
        raise HTTPException(
            status_code=409,
            detail=(
                f"{store.name} is closed right now. Opening hours: {hours}."
                if hours
                else f"{store.name} is closed right now."
            ),
        )

    listing_ids = sorted((item.store_product_id for item in items), key=str)
    locked_listings = db.scalars(
        select(StoreProduct)
        .where(StoreProduct.id.in_(listing_ids))
        .order_by(StoreProduct.id)
        .with_for_update()
    ).all()
    listings_by_id = {listing.id: listing for listing in locked_listings}

    if len(listings_by_id) != len(listing_ids):
        raise HTTPException(status_code=409, detail="Cart inventory changed; review your cart")

    subtotal = Decimal("0.00")
    validated: list[tuple[CartItem, StoreProduct]] = []
    for item in items:
        listing = listings_by_id[item.store_product_id]
        if listing.store_id != cart.store_id:
            raise HTTPException(status_code=409, detail="Cart inventory changed; review your cart")
        if not listing.is_available or listing.stock_quantity < item.quantity:
            raise HTTPException(status_code=409, detail="Cart inventory changed; review your cart")
        subtotal += listing.price * item.quantity
        validated.append((item, listing))

    delivery_fee = resolve_delivery_fee(db, store)
    order = Order(
        order_number=_new_order_number(),
        user_id=user.id,
        store_id=cart.store_id,
        address_id=address.id,
        idempotency_key=idempotency_key,
        delivery_address=_address_snapshot(address),
        payment_method=payload.payment_method,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total=order_total(subtotal, delivery_fee),
    )
    db.add(order)
    db.flush()

    for item, listing in validated:
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

    if order.payment_method == PaymentMethod.COD:
        _notify_customer(db, order)
        _notify_merchant(db, order, store)
    else:
        # An online order is only a payment reservation at this point.
        # Do not alert the merchant to prepare goods before verified capture.
        enqueue_notification(
            db,
            user_id=order.user_id,
            event_type="order.payment_pending",
            title="Payment pending",
            body=f"Complete payment for order {order.order_number} to confirm it.",
            data={"order_id": str(order.id), "order_number": order.order_number},
        )

    db.commit()
    db.refresh(order)
    return order
