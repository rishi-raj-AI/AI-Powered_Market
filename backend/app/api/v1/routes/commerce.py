import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.commerce import Category, Merchant, MerchantStatus, Product, Store, StoreProduct
from app.models.geography import ServiceArea, Village
from app.models.user import User, UserRole
from app.services.spatial import point_is_in_service_area
from app.services.store_hours import store_is_open
from app.schemas.commerce import (
    CategoryCreate,
    CategoryRead,
    MerchantCreate,
    MerchantRead,
    MerchantStatusUpdate,
    NearbyStoreRead,
    ProductCreate,
    ProductRead,
    StoreCreate,
    StoreProductCreate,
    StoreProductRead,
    StoreProductUpdate,
    StoreRead,
    StoreUpdate,
)

router = APIRouter(tags=["Commerce"])


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return earth_radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _merchant_for_store(db: Session, store: Store) -> Merchant | None:
    return db.get(Merchant, store.merchant_id)


def _require_store_owner(db: Session, store: Store, user: User) -> Merchant | None:
    merchant = _merchant_for_store(db, store)
    if user.role != UserRole.ADMIN and (merchant is None or merchant.owner_user_id != user.id):
        raise HTTPException(status_code=403, detail="You do not own this store")
    return merchant


def _store_read(store: Store) -> StoreRead:
    """Serialise a store with its backend-decided current availability."""
    payload = StoreRead.model_validate(store).model_dump()
    payload["is_open_now"] = store_is_open(store)
    return StoreRead(**payload)


def _public_store_stmt():
    return (
        select(Store)
        .join(Merchant, Store.merchant_id == Merchant.id)
        .where(Store.is_active.is_(True), Merchant.status == MerchantStatus.APPROVED)
    )


def _set_merchant_status(db: Session, merchant: Merchant, target: MerchantStatus) -> None:
    merchant.status = target
    if target == MerchantStatus.SUSPENDED:
        db.execute(update(Store).where(Store.merchant_id == merchant.id).values(is_active=False))
    elif target == MerchantStatus.APPROVED:
        db.execute(update(Store).where(Store.merchant_id == merchant.id).values(is_active=True))


@router.post("/merchants/apply", response_model=MerchantRead, status_code=status.HTTP_201_CREATED)
def apply_as_merchant(
    payload: MerchantCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
    if existing:
        raise HTTPException(status_code=409, detail="Merchant profile already exists")
    merchant = Merchant(owner_user_id=user.id, **payload.model_dump())
    user.role = UserRole.MERCHANT
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return merchant


@router.get("/merchants", response_model=list[MerchantRead])
def list_merchants(
    status_filter: MerchantStatus | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    stmt = select(Merchant).order_by(Merchant.created_at.desc())
    if status_filter is not None:
        stmt = stmt.where(Merchant.status == status_filter)
    return db.scalars(stmt).all()


@router.get("/merchants/me", response_model=MerchantRead)
def get_my_merchant(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
):
    merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
    if merchant is None:
        raise HTTPException(status_code=404, detail="Merchant profile not found")
    return merchant


@router.patch("/merchants/{merchant_id}/approve", response_model=MerchantRead)
def approve_merchant(
    merchant_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    merchant = db.get(Merchant, merchant_id)
    if merchant is None:
        raise HTTPException(status_code=404, detail="Merchant not found")
    _set_merchant_status(db, merchant, MerchantStatus.APPROVED)
    db.commit()
    db.refresh(merchant)
    return merchant


@router.patch("/merchants/{merchant_id}/status", response_model=MerchantRead)
def update_merchant_status(
    merchant_id: uuid.UUID,
    payload: MerchantStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    merchant = db.get(Merchant, merchant_id)
    if merchant is None:
        raise HTTPException(status_code=404, detail="Merchant not found")
    _set_merchant_status(db, merchant, payload.status)
    db.commit()
    db.refresh(merchant)
    return merchant


@router.post("/stores", response_model=StoreRead, status_code=status.HTTP_201_CREATED)
def create_store(
    payload: StoreCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
):
    merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
    if merchant is None:
        raise HTTPException(status_code=404, detail="Merchant profile not found")
    if merchant.status != MerchantStatus.APPROVED:
        raise HTTPException(status_code=403, detail="Merchant approval required")
    if db.get(Village, payload.village_id) is None:
        raise HTTPException(status_code=404, detail="Village not found")
    if payload.service_area_id:
        area = db.get(ServiceArea, payload.service_area_id)
        if area is None:
            raise HTTPException(status_code=404, detail="Service area not found")
        if not area.is_active:
            raise HTTPException(status_code=409, detail="Service area is not active")
        # Serviceability is checked at checkout as address-in-area. Without this
        # a merchant could attach a store to any area on the platform and become
        # the delivery option for every address in it.
        if payload.latitude is None or payload.longitude is None:
            raise HTTPException(
                status_code=422,
                detail="Pin the storefront location before assigning a service area",
            )
        if not point_is_in_service_area(
            db, payload.service_area_id, payload.latitude, payload.longitude
        ):
            raise HTTPException(
                status_code=422,
                detail="The storefront location is outside the selected service area",
            )
    if db.scalar(select(Store).where(Store.slug == payload.slug)):
        raise HTTPException(status_code=409, detail="Store slug already exists")
    store = Store(merchant_id=merchant.id, **payload.model_dump())
    db.add(store)
    db.commit()
    db.refresh(store)
    return _store_read(store)


@router.get("/stores", response_model=list[StoreRead])
def list_stores(
    village_id: uuid.UUID | None = None,
    q: str | None = None,
    delivery: bool | None = None,
    db: Session = Depends(get_db),
):
    stmt = _public_store_stmt().order_by(Store.name)
    if village_id:
        stmt = stmt.where(Store.village_id == village_id)
    if q:
        stmt = stmt.where(Store.name.ilike(f"%{q}%"))
    if delivery is not None:
        stmt = stmt.where(Store.delivery_enabled.is_(delivery))
    return [_store_read(store) for store in db.scalars(stmt).all()]


@router.get("/stores/nearby", response_model=list[NearbyStoreRead])
def nearby_stores(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=15, gt=0, le=100),
    delivery: bool | None = None,
    db: Session = Depends(get_db),
):
    stmt = _public_store_stmt().where(
        Store.latitude.is_not(None),
        Store.longitude.is_not(None),
    )
    if delivery is not None:
        stmt = stmt.where(Store.delivery_enabled.is_(delivery))

    results: list[NearbyStoreRead] = []
    for store in db.scalars(stmt).all():
        distance = _distance_km(lat, lng, float(store.latitude), float(store.longitude))
        if distance <= radius_km:
            payload = _store_read(store).model_dump()
            results.append(NearbyStoreRead(**payload, distance_km=round(distance, 2)))
    return sorted(results, key=lambda item: item.distance_km)


@router.get("/stores/mine", response_model=list[StoreRead])
def my_stores(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
):
    merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
    if merchant is None:
        return []
    return [
        _store_read(store)
        for store in db.scalars(
            select(Store).where(Store.merchant_id == merchant.id).order_by(Store.created_at.desc())
        ).all()
    ]


@router.get("/stores/{store_id}", response_model=StoreRead)
def get_store(store_id: uuid.UUID, db: Session = Depends(get_db)):
    store = db.scalar(_public_store_stmt().where(Store.id == store_id))
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return _store_read(store)


@router.patch("/stores/{store_id}", response_model=StoreRead)
def update_store(
    store_id: uuid.UUID,
    payload: StoreUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
):
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    merchant = _require_store_owner(db, store, user)
    if user.role != UserRole.ADMIN and merchant and merchant.status != MerchantStatus.APPROVED:
        raise HTTPException(status_code=403, detail="Merchant is not active")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(store, key, value)
    # Relocating a store must not silently move it out of the area it serves.
    if ("latitude" in updates or "longitude" in updates) and store.service_area_id is not None:
        if store.latitude is None or store.longitude is None:
            raise HTTPException(
                status_code=422,
                detail="A store with a service area must keep a pinned location",
            )
        if not point_is_in_service_area(
            db, store.service_area_id, float(store.latitude), float(store.longitude)
        ):
            db.rollback()
            raise HTTPException(
                status_code=422,
                detail="The new storefront location is outside this store's service area",
            )
    db.commit()
    db.refresh(store)
    return _store_read(store)


@router.post("/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    if db.scalar(
        select(Category).where((Category.name == payload.name) | (Category.slug == payload.slug))
    ):
        raise HTTPException(status_code=409, detail="Category already exists")
    category = Category(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.get("/categories", response_model=list[CategoryRead])
def list_categories(db: Session = Depends(get_db)):
    return db.scalars(
        select(Category).where(Category.is_active.is_(True)).order_by(Category.name)
    ).all()


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(status_code=404, detail="Category not found")
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/products", response_model=list[ProductRead])
def list_products(
    category_id: uuid.UUID | None = None,
    q: str | None = Query(default=None, min_length=1),
    db: Session = Depends(get_db),
):
    stmt = select(Product).where(Product.is_active.is_(True)).order_by(Product.name)
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    return db.scalars(stmt).all()


@router.post(
    "/stores/{store_id}/products",
    response_model=StoreProductRead,
    status_code=status.HTTP_201_CREATED,
)
def upsert_store_product(
    store_id: uuid.UUID,
    payload: StoreProductCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
):
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    merchant = _require_store_owner(db, store, user)
    if user.role != UserRole.ADMIN and (merchant is None or merchant.status != MerchantStatus.APPROVED):
        raise HTTPException(status_code=403, detail="Merchant is not active")
    if db.get(Product, payload.product_id) is None:
        raise HTTPException(status_code=404, detail="Product not found")
    listing = db.scalar(
        select(StoreProduct).where(
            StoreProduct.store_id == store_id,
            StoreProduct.product_id == payload.product_id,
        )
    )
    if listing:
        for key, value in payload.model_dump().items():
            setattr(listing, key, value)
    else:
        listing = StoreProduct(store_id=store_id, **payload.model_dump())
        db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


@router.patch(
    "/stores/{store_id}/products/{listing_id}",
    response_model=StoreProductRead,
)
def update_store_product(
    store_id: uuid.UUID,
    listing_id: uuid.UUID,
    payload: StoreProductUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
):
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    merchant = _require_store_owner(db, store, user)
    if user.role != UserRole.ADMIN and (merchant is None or merchant.status != MerchantStatus.APPROVED):
        raise HTTPException(status_code=403, detail="Merchant is not active")
    listing = db.scalar(
        select(StoreProduct).where(
            StoreProduct.id == listing_id,
            StoreProduct.store_id == store_id,
        )
    )
    if listing is None:
        raise HTTPException(status_code=404, detail="Store product not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(listing, key, value)
    db.commit()
    db.refresh(listing)
    return listing


@router.get("/stores/{store_id}/inventory", response_model=list[StoreProductRead])
def store_inventory(
    store_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
):
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    _require_store_owner(db, store, user)
    return db.scalars(
        select(StoreProduct)
        .where(StoreProduct.store_id == store_id)
        .order_by(StoreProduct.updated_at.desc())
    ).all()


@router.get("/stores/{store_id}/products", response_model=list[StoreProductRead])
def list_store_products(store_id: uuid.UUID, db: Session = Depends(get_db)):
    store = db.scalar(_public_store_stmt().where(Store.id == store_id))
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return db.scalars(
        select(StoreProduct)
        .where(
            StoreProduct.store_id == store_id,
            StoreProduct.is_available.is_(True),
            StoreProduct.stock_quantity > 0,
        )
        .order_by(StoreProduct.updated_at.desc())
    ).all()
