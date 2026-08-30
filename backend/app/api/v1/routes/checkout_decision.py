import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.commerce import Merchant, MerchantStatus, Store, StoreProduct
from app.models.geography import Address, Village
from app.models.orders import Cart, CartItem, Delivery, DeliveryStatus, Order, OrderStatus
from app.models.user import User
from app.services.pricing import checkout_totals
from app.services.spatial import point_is_in_service_area

router = APIRouter(tags=["Commerce Intelligence"])


def _address_point(db: Session, address: Address) -> tuple[float, float] | None:
    if address.latitude is not None and address.longitude is not None:
        return float(address.latitude), float(address.longitude)
    village = db.get(Village, address.village_id)
    if village and village.latitude is not None and village.longitude is not None:
        return float(village.latitude), float(village.longitude)
    return None


def _reliability(db: Session, store_id: uuid.UUID) -> tuple[float, int]:
    terminal_states = [OrderStatus.DELIVERED, OrderStatus.CANCELLED]
    counts = dict(
        db.execute(
            select(Order.status, func.count(Order.id))
            .where(Order.store_id == store_id, Order.status.in_(terminal_states))
            .group_by(Order.status)
        ).all()
    )
    delivered = int(counts.get(OrderStatus.DELIVERED, 0))
    cancelled = int(counts.get(OrderStatus.CANCELLED, 0))
    terminal_total = delivered + cancelled
    if terminal_total <= 0:
        return 0.5, 0
    failed = int(
        db.scalar(
            select(func.count(Delivery.id))
            .join(Order, Order.id == Delivery.order_id)
            .where(
                Order.store_id == store_id,
                Delivery.status == DeliveryStatus.FAILED,
                Order.status.in_(terminal_states),
            )
        )
        or 0
    )
    score = max(0.0, min(1.0, delivered / terminal_total - 0.45 * cancelled / terminal_total - 0.35 * failed / terminal_total))
    return round(score, 3), terminal_total


@router.get("/checkout/decision-summary")
def checkout_decision_summary(
    address_id: uuid.UUID = Query(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    address = db.get(Address, address_id)
    if address is None or address.user_id != user.id:
        raise HTTPException(status_code=404, detail="Address not found")

    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    if cart is None or cart.store_id is None:
        return {"ready": False, "blockers": ["cart_empty"], "warnings": [], "recommendation": "add_items"}

    store = db.get(Store, cart.store_id)
    merchant = db.get(Merchant, store.merchant_id) if store else None
    blockers: list[str] = []
    warnings: list[str] = []
    if store is None or not store.is_active or merchant is None or merchant.status != MerchantStatus.APPROVED:
        blockers.append("store_unavailable")

    rows = db.execute(
        select(CartItem, StoreProduct)
        .join(StoreProduct, StoreProduct.id == CartItem.store_product_id)
        .where(CartItem.cart_id == cart.id)
        .order_by(CartItem.id)
    ).all()
    subtotal = Decimal("0.00")
    for item, listing in rows:
        subtotal += listing.price * item.quantity
        if listing.store_id != cart.store_id or not listing.is_available or listing.stock_quantity < item.quantity:
            blockers.append(f"inventory:{item.store_product_id}")
        elif listing.stock_quantity <= max(item.quantity + 1, 3):
            warnings.append(f"low_stock:{item.store_product_id}")
    if not rows:
        blockers.append("cart_empty")

    point = _address_point(db, address)
    serviceable = False
    if store and store.delivery_enabled and store.service_area_id and point is not None:
        serviceable = point_is_in_service_area(db, store.service_area_id, point[0], point[1])
    if not serviceable:
        blockers.append("delivery_not_serviceable")

    reliability, sample_count = _reliability(db, cart.store_id)
    if sample_count >= 5 and reliability < 0.65:
        warnings.append("store_reliability_below_target")

    delivery_fee, total = checkout_totals(subtotal=subtotal, serviceable=serviceable)
    ready = not blockers
    if ready and warnings:
        recommendation = "review_then_checkout"
    elif ready:
        recommendation = "checkout"
    elif blockers == ["delivery_not_serviceable"] and store and store.pickup_enabled:
        recommendation = "switch_to_pickup"
    else:
        recommendation = "resolve_blockers"

    response = {
        "ready": ready,
        "store_id": str(cart.store_id),
        "address_id": str(address_id),
        "subtotal": str(subtotal.quantize(Decimal("0.01"))),
        "delivery_fee": str(delivery_fee),
        "total": str(total),
        "delivery_serviceable": serviceable,
        "merchant_reliability_samples": sample_count,
        "merchant_reliability_basis": "terminal_operational_history",
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "recommendation": recommendation,
    }
    if sample_count >= 5:
        response["merchant_reliability"] = reliability
    return response
