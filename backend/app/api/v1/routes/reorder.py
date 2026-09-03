import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.commerce import Merchant, MerchantStatus, Product, Store, StoreProduct
from app.models.orders import Order, OrderItem
from app.models.user import User

router = APIRouter(tags=["Commerce"])


class ReorderItemRead(BaseModel):
    product_id: uuid.UUID
    product_name: str
    requested_quantity: int
    available_quantity: int
    listing_id: uuid.UUID | None = None
    previous_unit_price: Decimal
    current_unit_price: Decimal | None = None
    available: bool


class ReorderPreviewRead(BaseModel):
    order_id: uuid.UUID
    store_id: uuid.UUID
    store_available: bool
    items: list[ReorderItemRead]
    available_items: int
    unavailable_items: int
    estimated_subtotal: Decimal


def _available_quantity(stock: int, requested: int, enabled: bool) -> int:
    return min(stock, requested) if enabled and stock > 0 else 0


@router.get("/orders/{order_id}/reorder-preview", response_model=ReorderPreviewRead)
def reorder_preview(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = db.get(Order, order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    store = db.get(Store, order.store_id)
    merchant = db.get(Merchant, store.merchant_id) if store else None
    store_available = bool(
        store
        and store.is_active
        and merchant
        and merchant.status == MerchantStatus.APPROVED
    )
    order_items = db.scalars(
        select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id)
    ).all()
    preview: list[ReorderItemRead] = []
    subtotal = Decimal("0.00")
    available_count = 0
    for item in order_items:
        listing = db.scalar(
            select(StoreProduct)
            .join(Product, Product.id == StoreProduct.product_id)
            .where(
                StoreProduct.store_id == order.store_id,
                StoreProduct.product_id == item.product_id,
                Product.is_active.is_(True),
            )
        )
        quantity = (
            0
            if listing is None or not store_available
            else _available_quantity(
                listing.stock_quantity, item.quantity, listing.is_available
            )
        )
        available = bool(listing is not None and quantity > 0)
        current_price = listing.price if listing is not None else None
        if available and current_price is not None:
            subtotal += current_price * quantity
            available_count += 1
        preview.append(
            ReorderItemRead(
                product_id=item.product_id,
                product_name=item.product_name,
                requested_quantity=item.quantity,
                available_quantity=quantity,
                listing_id=listing.id if listing else None,
                previous_unit_price=item.unit_price,
                current_unit_price=current_price,
                available=available,
            )
        )
    return ReorderPreviewRead(
        order_id=order.id,
        store_id=order.store_id,
        store_available=store_available,
        items=preview,
        available_items=available_count,
        unavailable_items=len(preview) - available_count,
        estimated_subtotal=subtotal,
    )
