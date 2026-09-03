import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.commerce import Merchant, MerchantStatus, Product, Store, StoreProduct

router = APIRouter(tags=["Commerce"])


class SubstitutionRead(BaseModel):
    listing_id: uuid.UUID
    product_id: uuid.UUID
    name: str
    brand: str | None = None
    unit: str
    price: Decimal
    price_delta: Decimal
    score: float


def _substitution_score(base_price: Decimal, candidate_price: Decimal, same_brand: bool) -> float:
    base = max(float(base_price), 1.0)
    price_penalty = min(abs(float(candidate_price - base_price)) / base, 1.0)
    return round((1.0 - price_penalty) + (0.25 if same_brand else 0.0), 4)


@router.get("/store-products/{listing_id}/substitutions", response_model=list[SubstitutionRead])
def substitutions(
    listing_id: uuid.UUID,
    limit: int = Query(default=5, ge=1, le=10),
    db: Session = Depends(get_db),
):
    base = db.scalar(
        select(StoreProduct)
        .join(Store, Store.id == StoreProduct.store_id)
        .join(Merchant, Merchant.id == Store.merchant_id)
        .where(
            StoreProduct.id == listing_id,
            Store.is_active.is_(True),
            Merchant.status == MerchantStatus.APPROVED,
        )
    )
    if base is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    base_product = db.get(Product, base.product_id)
    if base_product is None or not base_product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")
    rows = db.execute(
        select(StoreProduct, Product)
        .join(Product, Product.id == StoreProduct.product_id)
        .where(
            StoreProduct.store_id == base.store_id,
            StoreProduct.id != base.id,
            StoreProduct.is_available.is_(True),
            StoreProduct.stock_quantity > 0,
            Product.is_active.is_(True),
            Product.category_id == base_product.category_id,
        )
    ).all()
    ranked = []
    for listing, product in rows:
        same_brand = bool(
            base_product.brand
            and product.brand
            and base_product.brand.casefold() == product.brand.casefold()
        )
        ranked.append(
            SubstitutionRead(
                listing_id=listing.id,
                product_id=product.id,
                name=product.name,
                brand=product.brand,
                unit=product.unit,
                price=listing.price,
                price_delta=listing.price - base.price,
                score=_substitution_score(base.price, listing.price, same_brand),
            )
        )
    ranked.sort(key=lambda item: (-item.score, abs(item.price_delta), item.name.casefold()))
    return ranked[:limit]
