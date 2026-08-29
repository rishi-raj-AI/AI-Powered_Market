import math
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.orders import Delivery, DeliveryLocation, DeliveryStatus
from app.models.user import User, UserRole
from app.schemas.tracking import DeliveryLocationCreate, DeliveryLocationRead

router = APIRouter(tags=["Live Tracking"])
ACTIVE_TRACKING_STATUSES = {DeliveryStatus.ASSIGNED, DeliveryStatus.PICKED_UP}
MIN_LOCATION_INTERVAL_SECONDS = 5
MAX_PLAUSIBLE_SPEED_MPS = 55.0
MAX_REPORTED_SPEED_MPS = 60.0


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_008.8
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _read(location: DeliveryLocation) -> DeliveryLocationRead:
    return DeliveryLocationRead(
        id=location.id,
        delivery_id=location.delivery_id,
        latitude=location.latitude,
        longitude=location.longitude,
        accuracy_m=location.accuracy_m,
        heading_deg=location.heading_deg,
        speed_mps=location.speed_mps,
        recorded_at=location.recorded_at,
    )


@router.post("/delivery/{delivery_id}/location", response_model=DeliveryLocationRead, status_code=201)
def hardened_record_delivery_location(
    delivery_id: uuid.UUID,
    payload: DeliveryLocationCreate,
    db: Session = Depends(get_db),
    rider: User = Depends(require_roles(UserRole.DELIVERY)),
):
    delivery = db.scalar(select(Delivery).where(Delivery.id == delivery_id).with_for_update())
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if delivery.delivery_partner_id != rider.id:
        raise HTTPException(status_code=403, detail="Delivery is not assigned to you")
    if delivery.status not in ACTIVE_TRACKING_STATUSES:
        raise HTTPException(status_code=409, detail="Live location is only accepted during an active delivery")

    now = datetime.now(timezone.utc)
    recorded_at = payload.recorded_at.astimezone(timezone.utc)
    if recorded_at > now + timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="Location timestamp is too far in the future")
    if recorded_at < now - timedelta(minutes=30):
        raise HTTPException(status_code=422, detail="Location timestamp is too old")
    if payload.accuracy_m is not None and payload.accuracy_m > 500:
        raise HTTPException(status_code=422, detail="Location accuracy is too poor")
    if payload.speed_mps is not None and payload.speed_mps > MAX_REPORTED_SPEED_MPS:
        raise HTTPException(status_code=422, detail="Reported rider speed is implausible")

    latest = db.scalar(
        select(DeliveryLocation)
        .where(DeliveryLocation.delivery_id == delivery.id)
        .order_by(DeliveryLocation.recorded_at.desc())
        .limit(1)
        .with_for_update()
    )
    if latest is not None:
        previous_at = latest.recorded_at.astimezone(timezone.utc)
        if recorded_at <= previous_at:
            raise HTTPException(status_code=409, detail="Location timestamp must be newer than the previous update")
        elapsed = (recorded_at - previous_at).total_seconds()
        if elapsed < MIN_LOCATION_INTERVAL_SECONDS:
            raise HTTPException(status_code=429, detail="Location updates are limited to one every 5 seconds")
        distance = _distance_m(latest.latitude, latest.longitude, payload.latitude, payload.longitude)
        implied_speed = distance / elapsed
        if implied_speed > MAX_PLAUSIBLE_SPEED_MPS:
            raise HTTPException(status_code=422, detail="Location jump is physically implausible")

    location = DeliveryLocation(
        delivery_id=delivery.id,
        delivery_partner_id=rider.id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_m=payload.accuracy_m,
        heading_deg=payload.heading_deg,
        speed_mps=payload.speed_mps,
        recorded_at=recorded_at,
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return _read(location)
