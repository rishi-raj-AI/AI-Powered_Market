import uuid
from decimal import Decimal
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VillageCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    taluka: str | None = None
    district: str
    state: str
    pincode: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class VillageRead(VillageCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    is_active: bool
    created_at: datetime


class ServiceAreaCreate(BaseModel):
    name: str
    hub_village_id: uuid.UUID
    radius_km: float = Field(default=10.0, gt=0, le=100)
    #: Null keeps the configured platform default for this area.
    delivery_fee: Decimal | None = Field(default=None, ge=0, le=10000, decimal_places=2)


class ServiceAreaRead(ServiceAreaCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    is_active: bool
    created_at: datetime


class AddressCreate(BaseModel):
    village_id: uuid.UUID
    label: str = Field(default="Home", max_length=40)
    recipient_name: str | None = None
    phone: str | None = None
    house_details: str | None = None
    landmark: str = Field(min_length=2, max_length=240)
    directions: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_default: bool = False


class AddressRead(AddressCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PlaceSuggestion(BaseModel):
    place_id: str
    text: str
    structured_format: dict | None = None


class PlaceDetailsRead(BaseModel):
    place_id: str
    formatted_address: str | None = None
    address_components: list[dict] = []
    latitude: float | None = None
    longitude: float | None = None
    plus_code: str | None = None


class ReverseGeocodeRead(BaseModel):
    formatted_address: str | None = None
    place_id: str | None = None
    address_components: list[dict] = []


class ServiceabilityRead(BaseModel):
    serviceable: bool
    service_area_id: uuid.UUID | None = None
    service_area_name: str | None = None
    distance_km: float | None = None
    radius_km: float | None = None
