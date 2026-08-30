import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DeliveryEtaRead(BaseModel):
    order_id: uuid.UUID
    delivery_id: uuid.UUID
    delivery_status: str
    phase: str
    estimated_arrival_at: datetime | None = None
    eta_minutes: int | None = None
    remaining_distance_km: float | None = None
    telemetry_age_seconds: int | None = None
    confidence: str
    basis: list[str] = Field(default_factory=list)


class DeliveryPerformanceRead(BaseModel):
    window_days: int
    target_minutes: int
    total_deliveries: int
    delivered: int
    failed: int
    active: int
    failure_rate: float
    on_time_rate: float | None = None
    avg_assign_to_pickup_minutes: float | None = None
    median_assign_to_pickup_minutes: float | None = None
    avg_pickup_to_delivery_minutes: float | None = None
    median_pickup_to_delivery_minutes: float | None = None
    avg_created_to_delivery_minutes: float | None = None
    median_created_to_delivery_minutes: float | None = None
    p90_created_to_delivery_minutes: float | None = None
