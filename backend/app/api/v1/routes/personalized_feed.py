import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.commerce import Category, Merchant, MerchantStatus, Product, Store, StoreProduct
from app.models.orders import Order, OrderItem, OrderStatus
from app.models.user import User
from app.services.spatial import nearby_store_distances

router = APIRouter(tags=["Discovery"])


def _history_weight(order_count: int, quantity: int) -> float:
    return min(6.0, order_count * 1.5 + min(quantity, 12) * 0.2)


@router.get("/discovery/for-you")
def personalized_nearby_feed(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=20, gt=0, le=100),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    nearby = nearby_store_distances(db, latitude, longitude, radius_km)
    distance_by_store = {store_id: distance for store_id, distance in nearby}
    if not distance_by_store:
        return {"personalized": False, "items": []}

    history = db.execute(
        select(
            OrderItem.product_id,
            func.count(func.distinct(Order.id)).label("order_count"),
            func.sum(OrderItem.quantity).label("quantity"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.user_id == user.id, Order.status == OrderStatus.DELIVERED)
        .group_by(OrderItem.product_id)
    ).all()
    history_score = {row.product_id: _history_weight(int(row.order_count), int(row.quantity or 0)) for row in history}

    rows = db.execute(
        select(StoreProduct.id, StoreProduct.store_id, StoreProduct.price, StoreProduct.mrp, Product.id.label("product_id"), Product.name, Product.brand, Product.unit, Category.name.label("category_name"), Store.name.label("store_name"))
        .join(Product, Product.id == StoreProduct.product_id)
        .join(Category, Category.id == Product.category_id)
        .join(Store, Store.id == StoreProduct.store_id)
        .join(Merchant, Merchant.id == Store.merchant_id)
        .where(
            Store.id.in_(list(distance_by_store)),
            Store.is_active.is_(True),
            Merchant.status == MerchantStatus.APPROVED,
            Product.is_active.is_(True),
            StoreProduct.is_available.is_(True),
            StoreProduct.stock_quantity > 0,
        )
    ).all()

    items = []
    for row in rows:
        distance = distance_by_store[row.store_id]
        personal = history_score.get(row.product_id, 0.0)
        score = personal + max(0.0, 2.0 - distance / max(radius_km, 1))
        items.append({
            "listing_id": row.id,
            "product_id": row.product_id,
            "store_id": row.store_id,
            "store_name": row.store_name,
            "name": row.name,
            "brand": row.brand,
            "unit": row.unit,
            "category": row.category_name,
            "price": str(row.price),
            "mrp": None if row.mrp is None else str(row.mrp),
            "distance_km": round(distance, 2),
            "score": round(score, 3),
            "reason": "Based on your previous orders" if personal > 0 else "Popular nearby availability",
        })
    items.sort(key=lambda item: (-item["score"], item["distance_km"], item["name"].casefold()))
    return {"personalized": bool(history_score), "items": items[:limit]}
