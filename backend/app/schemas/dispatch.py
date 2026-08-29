import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RiderPresenceUpdate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    is_online: bool = True


class RiderPresenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rider_id: uuid.UUID
    latitude: float
    longitude: float
    is_online: bool
    last_seen_at: datetime


class AutoDispatchRequest(BaseModel):
    max_radius_km: float = Field(default=15.0, gt=0, le=100)


class AutoDispatchRead(BaseModel):
    delivery_id: uuid.UUID
    order_id: uuid.UUID
    rider_id: uuid.UUID
    rider_name: str | None = None
    distance_km: float
    assigned_at: datetime
