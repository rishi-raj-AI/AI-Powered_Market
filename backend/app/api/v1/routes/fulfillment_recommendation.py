import uuid
from datetime import datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.commerce import Merchant, MerchantStatus, Store
from app.services.spatial import point_is_in_service_area

router = APIRouter(tags=["Commerce Intelligence"])
INDIA_TZ = ZoneInfo("Asia/Kolkata")


def recommend_mode(*, delivery: bool, pickup: bool, serviceable: bool, is_open: bool) -> tuple[str, list[str]]:
    if delivery and serviceable and is_open: return "delivery_now", ["delivery_enabled", "serviceable", "store_open"]
    if pickup and is_open: return "pickup_now", ["pickup_enabled", "store_open"]
    if delivery and serviceable: return "scheduled_delivery", ["delivery_enabled", "serviceable", "store_closed_now"]
    if pickup: return "scheduled_pickup", ["pickup_enabled", "store_closed_now"]
    return "unavailable", ["no_supported_fulfillment_mode"]


def is_store_open(*, opens_at: time | None, closes_at: time | None, now: datetime | None = None) -> bool:
    if opens_at is None or closes_at is None: return True
    local_now = (now or datetime.now(INDIA_TZ)).astimezone(INDIA_TZ).time().replace(tzinfo=None)
    if opens_at <= closes_at: return opens_at <= local_now <= closes_at
    return local_now >= opens_at or local_now <= closes_at


@router.get("/stores/{store_id}/fulfillment-recommendation")
def fulfillment_recommendation(store_id: uuid.UUID, latitude: float = Query(ge=-90, le=90), longitude: float = Query(ge=-180, le=180), db: Session = Depends(get_db)):
    store = db.get(Store, store_id)
    merchant = db.get(Merchant, store.merchant_id) if store else None
    if store is None or not store.is_active or merchant is None or merchant.status != MerchantStatus.APPROVED: raise HTTPException(status_code=404, detail="Store not found")
    serviceable = bool(store.delivery_enabled and store.service_area_id and point_is_in_service_area(db, store.service_area_id, latitude, longitude))
    open_now = is_store_open(opens_at=store.opens_at, closes_at=store.closes_at)
    mode, reasons = recommend_mode(delivery=store.delivery_enabled, pickup=store.pickup_enabled, serviceable=serviceable, is_open=open_now)
    return {"store_id": str(store.id), "recommended_mode": mode, "delivery_enabled": bool(store.delivery_enabled), "pickup_enabled": bool(store.pickup_enabled), "delivery_serviceable": serviceable, "store_open": open_now, "timezone": "Asia/Kolkata", "reasons": reasons}
