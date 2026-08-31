import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.commerce import Merchant, MerchantStatus, Store, StoreProduct
from app.models.geography import Address, Village
from app.models.orders import Cart, CartItem, Delivery, Order, OrderItem
from app.models.user import User
from app.schemas.orders import CheckoutRequest, OrderRead
from app.services.notifications import enqueue_notification
from app.services.spatial import point_is_in_service_area
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


def _address_point(db: Session, address: Address) -> tuple[float, float] | None:
    if address.latitude is not None and address.longitude is not None:
        return float(address.latitude), float(address.longitude)
    village = db.get(Village, address.village_id)
    if village and village.latitude is not None and village.longitude is not None:
        return float(village.latitude), float(village.longitude)
    return None


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
            return existing

    address = db.get(Address, payload.address_id)
    if address is None or address.user_id != user.id:
        raise HTTPException(status_code=404, detail="Address not found")

    cart = db.scalar(select(Cart).where(Cart.user_id == user.id).with_for_update())

    existing = _existing_idempotent_order(db, user.id, idempotency_key)
    if existing:
        return existing

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
    if not store.delivery_enabled:
        raise HTTPException(status_code=409, detail="This store does not currently support delivery")
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

    address_point = _address_point(db, address)
    if store.service_area_id is None or address_point is None:
        raise HTTPException(status_code=409, detail="Delivery serviceability cannot be verified for this order")
    if not point_is_in_service_area(db, store.service_area_id, address_point[0], address_point[1]):
        raise HTTPException(status_code=409, detail="This store does not deliver to the selected address")

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

    delivery_fee = Decimal("20.00")
    order = Order(
        order_number=f"GO{datetime.now(timezone.utc).strftime('%y%m%d%H%M%S%f')[-14:]}",
        user_id=user.id,
        store_id=cart.store_id,
        address_id=address.id,
        idempotency_key=idempotency_key,
        payment_method=payload.payment_method,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total=subtotal + delivery_fee,
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

    _notify_customer(db, order)
    _notify_merchant(db, order, store)

    db.commit()
    db.refresh(order)
    return order
