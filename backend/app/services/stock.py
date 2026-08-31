"""Stock restoration for orders that will never be fulfilled.

Restoration is idempotent by design: ``Order.stock_restored_at`` is the guard,
so a cancellation followed by a post-pickup return cannot credit the same units
twice. Merchant availability decisions are respected — returning stock does not
re-list a product the merchant deliberately took down.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commerce import StoreProduct
from app.models.orders import Order, OrderItem


def restore_order_stock_once(db: Session, order: Order) -> bool:
    """Return an order's units to the store's inventory exactly once.

    Returns True when this call performed the restoration.
    """
    if order.stock_restored_at is not None:
        return False

    items = db.scalars(
        select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.product_id)
    ).all()
    if not items:
        order.stock_restored_at = datetime.now(timezone.utc)
        return True

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
        was_sold_out = listing.stock_quantity == 0
        listing.stock_quantity += item.quantity
        # Only undo the automatic sold-out flag that checkout set. A listing the
        # merchant switched off stays off.
        if was_sold_out and not listing.is_available:
            listing.is_available = True

    order.stock_restored_at = datetime.now(timezone.utc)
    return True
