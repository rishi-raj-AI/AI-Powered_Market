import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.orders import DeliveryStatus, OrderStatus


class DeliveryLocationCreate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, le=5000)
    heading_deg: float | None = Field(default=None, ge=0, lt=360)
    speed_mps: float | None = Field(default=None, ge=0, le=100)
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("recorded_at must include a timezone")
        return value


class DeliveryLocationRead(BaseModel):
    id: uuid.UUID
    delivery_id: uuid.UUID
    latitude: float
    longitude: float
    accuracy_m: float | None = None
    heading_deg: float | None = None
    speed_mps: float | None = None
    recorded_at: datetime


class TrackingPoint(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    label: str | None = None


class OrderTrackingRead(BaseModel):
    order_id: uuid.UUID
    order_number: str
    order_status: OrderStatus
    delivery_id: uuid.UUID | None = None
    delivery_status: DeliveryStatus | None = None
    tracking_active: bool
    store: TrackingPoint
    customer: TrackingPoint
    rider: DeliveryLocationRead | None = None
    rider_location_age_seconds: int | None = None
