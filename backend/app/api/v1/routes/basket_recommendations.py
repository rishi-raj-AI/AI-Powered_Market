from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.commerce import Category, Product, StoreProduct
from app.models.orders import Cart, CartItem
from app.models.user import User

router = APIRouter(tags=["Cart"])


def _basket_score(category_match: bool, stock_quantity: int, price: float) -> float:
    return (3.0 if category_match else 1.0) + min(stock_quantity, 20) * 0.03 + max(0.0, 1.0 - price / 1000.0)


@router.get("/cart/recommendations")
def basket_recommendations(
    limit: int = Query(default=8, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    if cart is None or cart.store_id is None:
        return {"store_id": None, "items": []}

    current_rows = db.execute(
        select(CartItem.store_product_id, Product.category_id)
        .join(StoreProduct, StoreProduct.id == CartItem.store_product_id)
        .join(Product, Product.id == StoreProduct.product_id)
        .where(CartItem.cart_id == cart.id)
    ).all()
    current_listing_ids = {row.store_product_id for row in current_rows}
    category_ids = {row.category_id for row in current_rows}

    candidates = db.execute(
        select(StoreProduct.id, StoreProduct.price, StoreProduct.mrp, StoreProduct.stock_quantity, Product.id.label("product_id"), Product.name, Product.brand, Product.unit, Product.category_id, Category.name.label("category_name"))
        .join(Product, Product.id == StoreProduct.product_id)
        .join(Category, Category.id == Product.category_id)
        .where(
            StoreProduct.store_id == cart.store_id,
            StoreProduct.is_available.is_(True),
            StoreProduct.stock_quantity > 0,
            Product.is_active.is_(True),
            ~StoreProduct.id.in_(current_listing_ids) if current_listing_ids else True,
        )
    ).all()

    items = []
    for row in candidates:
        score = _basket_score(row.category_id in category_ids, row.stock_quantity, float(row.price))
        items.append({
            "listing_id": row.id,
            "product_id": row.product_id,
            "name": row.name,
            "brand": row.brand,
            "unit": row.unit,
            "category": row.category_name,
            "price": str(row.price),
            "mrp": None if row.mrp is None else str(row.mrp),
            "stock_quantity": row.stock_quantity,
            "score": round(score, 3),
            "reason": "Complements items already in your basket" if row.category_id in category_ids else "Available from the same store",
        })
    items.sort(key=lambda item: (-item["score"], item["name"].casefold()))
    return {"store_id": cart.store_id, "items": items[:limit]}
