import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.commerce import Merchant, MerchantStatus, Store
from app.services.spatial import point_is_in_service_area

router = APIRouter(tags=["Commerce Intelligence"])


def recommend_mode(*, delivery: bool, pickup: bool, serviceable: bool, is_open: bool) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if delivery and serviceable and is_open:
        return "delivery_now", ["delivery_enabled", "serviceable", "store_open"]
    if pickup and is_open:
        return "pickup_now", ["pickup_enabled", "store_open"]
    if delivery and serviceable:
        reasons.extend(["delivery_enabled", "serviceable", "store_closed_now"])
        return "scheduled_delivery", reasons
    if pickup:
        return "scheduled_pickup", ["pickup_enabled", "store_closed_now"]
    return "unavailable", ["no_supported_fulfillment_mode"]


@router.get("/stores/{store_id}/fulfillment-recommendation")
def fulfillment_recommendation(
    store_id: uuid.UUID,
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    db: Session = Depends(get_db),
):
    store = db.get(Store, store_id)
    merchant = db.get(Merchant, store.merchant_id) if store else None
    if store is None or not store.is_active or merchant is None or merchant.status != MerchantStatus.APPROVED:
        raise HTTPException(status_code=404, detail="Store not found")

    serviceable = bool(
        store.delivery_enabled
        and store.service_area_id
        and point_is_in_service_area(db, store.service_area_id, latitude, longitude)
    )
    now = datetime.now(timezone.utc).time().replace(tzinfo=None)
    if store.opens_at is None or store.closes_at is None:
        is_open = True
    elif store.opens_at <= store.closes_at:
        is_open = store.opens_at <= now <= store.closes_at
    else:
        is_open = now >= store.opens_at or now <= store.closes_at

    mode, reasons = recommend_mode(
        delivery=store.delivery_enabled,
        pickup=store.pickup_enabled,
        serviceable=serviceable,
        is_open=is_open,
    )
    return {
        "store_id": str(store.id),
        "recommended_mode": mode,
        "delivery_serviceable": serviceable,
        "store_open": is_open,
        "reasons": reasons,
    }
