import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.commerce import Category, Merchant, MerchantStatus, Product, Store, StoreProduct
from app.models.geography import ServiceArea, Village
from app.models.user import User, UserRole
from app.schemas.commerce import CategoryCreate, CategoryRead, MerchantCreate, MerchantRead, ProductCreate, ProductRead, StoreCreate, StoreProductCreate, StoreProductRead, StoreRead

router = APIRouter(tags=["Commerce"])


@router.post("/merchants/apply", response_model=MerchantRead, status_code=status.HTTP_201_CREATED)
def apply_as_merchant(payload: MerchantCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    existing = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
    if existing:
        raise HTTPException(status_code=409, detail="Merchant profile already exists")
    merchant = Merchant(owner_user_id=user.id, **payload.model_dump())
    user.role = UserRole.MERCHANT
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return merchant


@router.get("/merchants/me", response_model=MerchantRead)
def get_my_merchant(db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN))):
    merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
    if merchant is None:
        raise HTTPException(status_code=404, detail="Merchant profile not found")
    return merchant


@router.patch("/merchants/{merchant_id}/approve", response_model=MerchantRead)
def approve_merchant(merchant_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.ADMIN))):
    merchant = db.get(Merchant, merchant_id)
    if merchant is None:
        raise HTTPException(status_code=404, detail="Merchant not found")
    merchant.status = MerchantStatus.APPROVED
    db.commit()
    db.refresh(merchant)
    return merchant


@router.post("/stores", response_model=StoreRead, status_code=status.HTTP_201_CREATED)
def create_store(payload: StoreCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN))):
    merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
    if merchant is None:
        raise HTTPException(status_code=404, detail="Merchant profile not found")
    if merchant.status != MerchantStatus.APPROVED and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Merchant approval required")
    if db.get(Village, payload.village_id) is None:
        raise HTTPException(status_code=404, detail="Village not found")
    if payload.service_area_id and db.get(ServiceArea, payload.service_area_id) is None:
        raise HTTPException(status_code=404, detail="Service area not found")
    if db.scalar(select(Store).where(Store.slug == payload.slug)):
        raise HTTPException(status_code=409, detail="Store slug already exists")
    store = Store(merchant_id=merchant.id, **payload.model_dump())
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


@router.get("/stores", response_model=list[StoreRead])
def list_stores(village_id: uuid.UUID | None = None, q: str | None = None, delivery: bool | None = None, db: Session = Depends(get_db)):
    stmt = select(Store).where(Store.is_active.is_(True)).order_by(Store.name)
    if village_id:
        stmt = stmt.where(Store.village_id == village_id)
    if q:
        stmt = stmt.where(Store.name.ilike(f"%{q}%"))
    if delivery is not None:
        stmt = stmt.where(Store.delivery_enabled.is_(delivery))
    return db.scalars(stmt).all()


@router.get("/stores/{store_id}", response_model=StoreRead)
def get_store(store_id: uuid.UUID, db: Session = Depends(get_db)):
    store = db.get(Store, store_id)
    if store is None or not store.is_active:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.post("/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.ADMIN))):
    if db.scalar(select(Category).where((Category.name == payload.name) | (Category.slug == payload.slug))):
        raise HTTPException(status_code=409, detail="Category already exists")
    category = Category(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.get("/categories", response_model=list[CategoryRead])
def list_categories(db: Session = Depends(get_db)):
    return db.scalars(select(Category).where(Category.is_active.is_(True)).order_by(Category.name)).all()


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.ADMIN))):
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(status_code=404, detail="Category not found")
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/products", response_model=list[ProductRead])
def list_products(category_id: uuid.UUID | None = None, q: str | None = Query(default=None, min_length=1), db: Session = Depends(get_db)):
    stmt = select(Product).where(Product.is_active.is_(True)).order_by(Product.name)
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    return db.scalars(stmt).all()


@router.post("/stores/{store_id}/products", response_model=StoreProductRead, status_code=status.HTTP_201_CREATED)
def upsert_store_product(store_id: uuid.UUID, payload: StoreProductCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN))):
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    merchant = db.get(Merchant, store.merchant_id)
    if user.role != UserRole.ADMIN and (merchant is None or merchant.owner_user_id != user.id):
        raise HTTPException(status_code=403, detail="You do not own this store")
    if db.get(Product, payload.product_id) is None:
        raise HTTPException(status_code=404, detail="Product not found")
    listing = db.scalar(select(StoreProduct).where(StoreProduct.store_id == store_id, StoreProduct.product_id == payload.product_id))
    if listing:
        for key, value in payload.model_dump().items():
            setattr(listing, key, value)
    else:
        listing = StoreProduct(store_id=store_id, **payload.model_dump())
        db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


@router.get("/stores/{store_id}/products", response_model=list[StoreProductRead])
def list_store_products(store_id: uuid.UUID, db: Session = Depends(get_db)):
    if db.get(Store, store_id) is None:
        raise HTTPException(status_code=404, detail="Store not found")
    stmt = select(StoreProduct).where(StoreProduct.store_id == store_id, StoreProduct.is_available.is_(True)).order_by(StoreProduct.updated_at.desc())
    return db.scalars(stmt).all()
