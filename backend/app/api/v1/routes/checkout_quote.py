import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.commerce import Merchant, MerchantStatus, Store, StoreProduct
from app.models.geography import Address, Village
from app.models.orders import Cart, CartItem
from app.models.user import User
from app.services.pricing import checkout_totals
from app.services.spatial import point_is_in_service_area

router = APIRouter(tags=["Orders & Checkout"])


def _address_point(db: Session, address: Address) -> tuple[float, float] | None:
    if address.latitude is not None and address.longitude is not None:
        return float(address.latitude), float(address.longitude)
    village = db.get(Village, address.village_id)
    if village and village.latitude is not None and village.longitude is not None:
        return float(village.latitude), float(village.longitude)
    return None


@router.get("/cart/quote")
def checkout_quote(
    address_id: uuid.UUID = Query(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    address = db.get(Address, address_id)
    if address is None or address.user_id != user.id:
        raise HTTPException(status_code=404, detail="Address not found")
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    if cart is None or cart.store_id is None:
        raise HTTPException(status_code=400, detail="Cart is empty")
    store = db.get(Store, cart.store_id)
    merchant = db.get(Merchant, store.merchant_id) if store else None
    if store is None or not store.is_active or merchant is None or merchant.status != MerchantStatus.APPROVED:
        raise HTTPException(status_code=409, detail="Store is currently unavailable")

    rows = db.execute(
        select(CartItem.quantity, StoreProduct.price, StoreProduct.stock_quantity, StoreProduct.is_available, StoreProduct.store_id)
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

    point = _address_point(db, address)
    serviceable = bool(
        store.delivery_enabled
        and store.service_area_id is not None
        and point is not None
        and point_is_in_service_area(db, store.service_area_id, point[0], point[1])
    )
    fee, total = checkout_totals(subtotal=subtotal, serviceable=serviceable)
    blockers = []
    if not inventory_valid:
        blockers.append("Cart inventory changed; review your cart")
    if not store.delivery_enabled:
        blockers.append("This store does not currently support delivery")
    elif not serviceable:
        blockers.append("This store does not deliver to the selected address")

    return {
        "store_id": store.id,
        "address_id": address.id,
        "subtotal": str(subtotal.quantize(Decimal("0.01"))),
        "delivery_fee": str(fee),
        "total": str(total),
        "serviceable": serviceable,
        "inventory_valid": inventory_valid,
        "checkout_ready": serviceable and inventory_valid,
        "blockers": blockers,
    }
