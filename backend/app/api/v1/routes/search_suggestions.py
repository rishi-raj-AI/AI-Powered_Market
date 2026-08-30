from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.commerce import Category, Merchant, MerchantStatus, Product, Store, StoreProduct
from app.services.spatial import nearby_store_distances

router = APIRouter(tags=["Discovery"])


class SearchSuggestion(BaseModel):
    kind: str
    label: str
    secondary: str | None = None
    store_id: str | None = None
    product_id: str | None = None
    category_id: str | None = None
    distance_km: float | None = None


def _prefix_rank(value: str | None, query: str) -> int:
    if not value:
        return 99
    value_cf = value.casefold()
    query_cf = query.casefold()
    if value_cf == query_cf:
        return 0
    if value_cf.startswith(query_cf):
        return 1
    if query_cf in value_cf:
        return 2
    return 99


@router.get("/discovery/suggestions", response_model=list[SearchSuggestion])
def discovery_suggestions(
    q: str = Query(min_length=1, max_length=80),
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=20, gt=0, le=100),
    limit: int = Query(default=8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    nearby = nearby_store_distances(db, latitude, longitude, radius_km)
    distance_by_store = {store_id: distance for store_id, distance in nearby}
    if not distance_by_store:
        return []
    store_ids = list(distance_by_store)
    items: list[tuple[tuple, SearchSuggestion]] = []

    for store in db.scalars(
        select(Store)
        .join(Merchant, Merchant.id == Store.merchant_id)
        .where(
            Store.id.in_(store_ids),
            Store.is_active.is_(True),
            Merchant.status == MerchantStatus.APPROVED,
            or_(Store.name.ilike(f"%{q}%"), Store.landmark.ilike(f"%{q}%")),
        )
    ).all():
        distance = distance_by_store[store.id]
        items.append((( _prefix_rank(store.name, q), distance, store.name.casefold()), SearchSuggestion(
            kind="store", label=store.name, secondary=store.landmark, store_id=str(store.id), distance_km=round(distance, 2)
        )))

    product_rows = db.execute(
        select(Product, Store, Category)
        .join(StoreProduct, StoreProduct.product_id == Product.id)
        .join(Store, Store.id == StoreProduct.store_id)
        .join(Merchant, Merchant.id == Store.merchant_id)
        .join(Category, Category.id == Product.category_id)
        .where(
            Store.id.in_(store_ids),
            Store.is_active.is_(True),
            Merchant.status == MerchantStatus.APPROVED,
            StoreProduct.is_available.is_(True),
            StoreProduct.stock_quantity > 0,
            Product.is_active.is_(True),
            Category.is_active.is_(True),
            or_(Product.name.ilike(f"%{q}%"), Product.brand.ilike(f"%{q}%"), Category.name.ilike(f"%{q}%")),
        )
    ).all()
    seen_products: set[tuple[str, str]] = set()
    for product, store, category in product_rows:
        dedupe = (str(product.id), str(store.id))
        if dedupe in seen_products:
            continue
        seen_products.add(dedupe)
        distance = distance_by_store[store.id]
        rank = min(_prefix_rank(product.name, q), _prefix_rank(product.brand, q), _prefix_rank(category.name, q))
        items.append(((rank, distance, product.name.casefold()), SearchSuggestion(
            kind="product", label=product.name, secondary=f"{store.name} • {category.name}", store_id=str(store.id), product_id=str(product.id), category_id=str(category.id), distance_km=round(distance, 2)
        )))

    items.sort(key=lambda pair: pair[0])
    return [suggestion for _, suggestion in items[:limit]]
