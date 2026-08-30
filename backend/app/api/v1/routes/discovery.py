import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.commerce import Category, Merchant, MerchantStatus, Product, Store, StoreProduct
from app.schemas.discovery import DiscoveryCategoryRead, DiscoveryProductRead, DiscoverySearchRead, DiscoveryStoreRead
from app.services.spatial import nearby_store_distances

router = APIRouter(tags=["Discovery"])


def _text_score(value: str | None, query: str) -> float:
    if not value:
        return 0.0
    haystack = value.casefold()
    needle = query.casefold()
    if haystack == needle:
        return 4.0
    if haystack.startswith(needle):
        return 3.0
    if needle in haystack:
        return 2.0
    return 0.0


@router.get("/discovery/search", response_model=DiscoverySearchRead)
def discovery_search(
    q: str = Query(min_length=1, max_length=120),
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=20, gt=0, le=100),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    nearby = nearby_store_distances(db, latitude, longitude, radius_km)
    distance_by_store = {store_id: distance for store_id, distance in nearby}
    if not distance_by_store:
        return DiscoverySearchRead(query=q, latitude=latitude, longitude=longitude, radius_km=radius_km, stores=[], products=[], categories=[])

    store_ids = list(distance_by_store)
    store_rows = db.execute(
        select(Store.id, Store.name, Store.landmark, Store.delivery_enabled)
        .join(Merchant, Store.merchant_id == Merchant.id)
        .where(
            Store.id.in_(store_ids),
            Store.is_active.is_(True),
            Merchant.status == MerchantStatus.APPROVED,
            or_(Store.name.ilike(f"%{q}%"), Store.description.ilike(f"%{q}%"), Store.landmark.ilike(f"%{q}%")),
        )
    ).all()
    stores = [
        DiscoveryStoreRead(
            id=row.id,
            name=row.name,
            landmark=row.landmark,
            delivery_enabled=row.delivery_enabled,
            distance_km=round(distance_by_store[row.id], 2),
            match_score=round(_text_score(row.name, q) + max(0.0, 2.0 - distance_by_store[row.id] / max(radius_km, 1)), 3),
        )
        for row in store_rows
    ]
    stores.sort(key=lambda item: (-item.match_score, item.distance_km, item.name.casefold()))

    product_rows = db.execute(
        select(
            StoreProduct.id.label("listing_id"),
            Product.id.label("product_id"),
            Store.id.label("store_id"),
            Store.name.label("store_name"),
            Product.name,
            Product.brand,
            Product.unit,
            StoreProduct.price,
            StoreProduct.mrp,
            Category.name.label("category_name"),
        )
        .join(Product, Product.id == StoreProduct.product_id)
        .join(Category, Category.id == Product.category_id)
        .join(Store, Store.id == StoreProduct.store_id)
        .join(Merchant, Merchant.id == Store.merchant_id)
        .where(
            Store.id.in_(store_ids),
            Store.is_active.is_(True),
            Merchant.status == MerchantStatus.APPROVED,
            StoreProduct.is_available.is_(True),
            StoreProduct.stock_quantity > 0,
            Product.is_active.is_(True),
            Category.is_active.is_(True),
            or_(
                Product.name.ilike(f"%{q}%"),
                Product.brand.ilike(f"%{q}%"),
                Product.description.ilike(f"%{q}%"),
                Category.name.ilike(f"%{q}%"),
                Store.name.ilike(f"%{q}%"),
            ),
        )
    ).all()
    products = []
    for row in product_rows:
        distance = distance_by_store[row.store_id]
        semantic_score = max(
            _text_score(row.name, q),
            _text_score(row.brand, q),
            _text_score(row.category_name, q),
            _text_score(row.store_name, q),
        )
        products.append(
            DiscoveryProductRead(
                listing_id=row.listing_id,
                product_id=row.product_id,
                store_id=row.store_id,
                store_name=row.store_name,
                name=row.name,
                brand=row.brand,
                unit=row.unit,
                price=row.price,
                mrp=row.mrp,
                distance_km=round(distance, 2),
                match_score=round(semantic_score + max(0.0, 2.0 - distance / max(radius_km, 1)), 3),
            )
        )
    products.sort(key=lambda item: (-item.match_score, item.distance_km, item.name.casefold(), item.store_name.casefold()))

    category_rows = db.execute(
        select(Category.id, Category.name, Category.slug, func.count(StoreProduct.id).label("listing_count"))
        .join(Product, Product.category_id == Category.id)
        .join(StoreProduct, StoreProduct.product_id == Product.id)
        .join(Store, Store.id == StoreProduct.store_id)
        .join(Merchant, Merchant.id == Store.merchant_id)
        .where(
            Store.id.in_(store_ids),
            Store.is_active.is_(True),
            Merchant.status == MerchantStatus.APPROVED,
            StoreProduct.is_available.is_(True),
            StoreProduct.stock_quantity > 0,
            Product.is_active.is_(True),
            Category.is_active.is_(True),
            Category.name.ilike(f"%{q}%"),
        )
        .group_by(Category.id, Category.name, Category.slug)
        .order_by(func.count(StoreProduct.id).desc(), Category.name)
    ).all()
    categories = [DiscoveryCategoryRead(id=row.id, name=row.name, slug=row.slug, available_listing_count=row.listing_count) for row in category_rows[:limit]]

    return DiscoverySearchRead(
        query=q,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        stores=stores[:limit],
        products=products[:limit],
        categories=categories,
    )
