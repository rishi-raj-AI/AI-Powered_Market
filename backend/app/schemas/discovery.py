import uuid
from decimal import Decimal

from pydantic import BaseModel


class DiscoveryStoreRead(BaseModel):
    id: uuid.UUID
    name: str
    landmark: str | None = None
    delivery_enabled: bool
    distance_km: float
    match_score: float


class DiscoveryProductRead(BaseModel):
    listing_id: uuid.UUID
    product_id: uuid.UUID
    store_id: uuid.UUID
    store_name: str
    name: str
    brand: str | None = None
    unit: str
    price: Decimal
    mrp: Decimal | None = None
    distance_km: float
    match_score: float


class DiscoveryCategoryRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    available_listing_count: int


class DiscoverySearchRead(BaseModel):
    query: str
    latitude: float
    longitude: float
    radius_km: float
    stores: list[DiscoveryStoreRead]
    products: list[DiscoveryProductRead]
    categories: list[DiscoveryCategoryRead]
