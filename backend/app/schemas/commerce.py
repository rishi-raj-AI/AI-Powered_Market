import uuid
from datetime import datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.commerce import MerchantStatus


class MerchantCreate(BaseModel):
    business_name: str = Field(min_length=2, max_length=160)
    gstin: str | None = None


class MerchantRead(MerchantCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_user_id: uuid.UUID
    status: MerchantStatus
    created_at: datetime
    updated_at: datetime


class StoreCreate(BaseModel):
    village_id: uuid.UUID
    service_area_id: uuid.UUID | None = None
    name: str
    slug: str
    description: str | None = None
    phone: str | None = None
    landmark: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    opens_at: time | None = None
    closes_at: time | None = None
    delivery_enabled: bool = True
    pickup_enabled: bool = True


class StoreRead(StoreCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    merchant_id: uuid.UUID
    is_active: bool
    created_at: datetime


class CategoryCreate(BaseModel):
    name: str
    slug: str


class CategoryRead(CategoryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    is_active: bool


class ProductCreate(BaseModel):
    category_id: uuid.UUID
    name: str
    description: str | None = None
    brand: str | None = None
    unit: str
    image_url: str | None = None


class ProductRead(ProductCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    is_active: bool
    created_at: datetime


class StoreProductCreate(BaseModel):
    product_id: uuid.UUID
    price: Decimal = Field(gt=0)
    mrp: Decimal | None = Field(default=None, gt=0)
    stock_quantity: int = Field(default=0, ge=0)
    is_available: bool = True


class StoreProductRead(StoreProductCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    store_id: uuid.UUID
    updated_at: datetime
    product: ProductRead
