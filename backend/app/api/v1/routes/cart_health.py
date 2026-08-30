import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.commerce import StoreProduct
from app.models.orders import Cart, CartItem
from app.models.user import User

router = APIRouter(tags=["Commerce Intelligence"])


def assess_cart_item(*, requested: int, stock: int, available: bool, price: Decimal) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if not available or stock <= 0:
        return "blocked", ["unavailable"]
    if stock < requested:
        return "blocked", ["insufficient_stock"]
    if stock <= max(requested + 1, 3):
        reasons.append("low_stock")
    if price <= 0:
        reasons.append("invalid_price")
    return ("warning" if reasons else "healthy"), reasons


@router.get("/cart/health")
def cart_health(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    if cart is None or cart.store_id is None:
        return {"status": "empty", "items": [], "blockers": [], "warnings": []}

    rows = db.execute(
        select(CartItem, StoreProduct)
        .join(StoreProduct, StoreProduct.id == CartItem.store_product_id)
        .where(CartItem.cart_id == cart.id)
        .order_by(CartItem.id)
    ).all()
    if not rows:
        return {"status": "empty", "items": [], "blockers": [], "warnings": []}

    items = []
    blockers: list[str] = []
    warnings: list[str] = []
    subtotal = Decimal("0.00")
    for item, listing in rows:
        state, reasons = assess_cart_item(
            requested=item.quantity,
            stock=listing.stock_quantity,
            available=listing.is_available,
            price=listing.price,
        )
        subtotal += listing.price * min(item.quantity, max(listing.stock_quantity, 0))
        if state == "blocked":
            blockers.extend(f"{item.store_product_id}:{reason}" for reason in reasons)
        elif state == "warning":
            warnings.extend(f"{item.store_product_id}:{reason}" for reason in reasons)
        items.append({
            "listing_id": str(item.store_product_id),
            "requested_quantity": item.quantity,
            "stock_quantity": listing.stock_quantity,
            "price": str(listing.price),
            "state": state,
            "reasons": reasons,
        })

    status = "blocked" if blockers else ("warning" if warnings else "healthy")
    return {
        "status": status,
        "store_id": str(cart.store_id),
        "subtotal": str(subtotal),
        "items": items,
        "blockers": blockers,
        "warnings": warnings,
    }
