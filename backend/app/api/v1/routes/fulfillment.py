from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.commerce import Merchant, MerchantStatus, Store
from app.services.places import distance_km
from app.services.spatial import point_is_in_service_area

router = APIRouter(tags=["Fulfillment"])


class FulfillmentModeRead(BaseModel):
    mode: str
    available: bool
    reason: str | None = None
    eta_min_minutes: int | None = None
    eta_max_minutes: int | None = None


class FulfillmentPromiseRead(BaseModel):
    store_id: uuid.UUID
    distance_km: float | None = None
    modes: list[FulfillmentModeRead]


def _eta_band(distance: float) -> tuple[int, int]:
    travel = max(8, round(distance / 18 * 60))
    prep = 20
    minimum = prep + travel
    return minimum, minimum + 15


@router.get('/stores/{store_id}/fulfillment-promise', response_model=FulfillmentPromiseRead)
def fulfillment_promise(
    store_id: uuid.UUID,
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    db: Session = Depends(get_db),
):
    store = db.scalar(
        select(Store)
        .join(Merchant, Merchant.id == Store.merchant_id)
        .where(Store.id == store_id, Store.is_active.is_(True), Merchant.status == MerchantStatus.APPROVED)
    )
    if store is None:
        raise HTTPException(status_code=404, detail='Store not found')

    distance: float | None = None
    if store.latitude is not None and store.longitude is not None:
        distance = distance_km(float(store.latitude), float(store.longitude), latitude, longitude)

    now = datetime.now(timezone.utc).time().replace(tzinfo=None)
    store_open = True
    if store.opens_at and store.closes_at:
        if store.opens_at <= store.closes_at:
            store_open = store.opens_at <= now <= store.closes_at
        else:
            store_open = now >= store.opens_at or now <= store.closes_at

    delivery_available = bool(store.delivery_enabled and store_open and distance is not None)
    delivery_reason: str | None = None
    if not store.delivery_enabled:
        delivery_reason = 'Store does not offer delivery'
    elif not store_open:
        delivery_reason = 'Store is currently closed'
    elif distance is None:
        delivery_reason = 'Store location is unavailable'
    elif store.service_area_id and not point_is_in_service_area(db, store.service_area_id, latitude, longitude):
        delivery_available = False
        delivery_reason = 'Selected location is outside this store service area'

    eta_min = eta_max = None
    if delivery_available and distance is not None:
        eta_min, eta_max = _eta_band(distance)

    pickup_available = bool(store.pickup_enabled and store_open)
    pickup_reason = None if pickup_available else ('Store does not offer pickup' if not store.pickup_enabled else 'Store is currently closed')

    return FulfillmentPromiseRead(
        store_id=store.id,
        distance_km=None if distance is None else round(distance, 2),
        modes=[
            FulfillmentModeRead(mode='delivery', available=delivery_available, reason=delivery_reason, eta_min_minutes=eta_min, eta_max_minutes=eta_max),
            FulfillmentModeRead(mode='pickup', available=pickup_available, reason=pickup_reason),
        ],
    )
