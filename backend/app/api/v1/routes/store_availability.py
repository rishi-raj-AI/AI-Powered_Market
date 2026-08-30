import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.commerce import Store

router = APIRouter(tags=["Commerce"])
INDIA_TZ = ZoneInfo("Asia/Kolkata")


def _availability(store: Store, now: datetime) -> dict:
    local_now = now.astimezone(INDIA_TZ)
    if store.opens_at is None or store.closes_at is None:
        return {
            "is_open": True,
            "status": "hours_not_configured",
            "minutes_until_close": None,
            "next_open_at": None,
        }

    open_dt = local_now.replace(hour=store.opens_at.hour, minute=store.opens_at.minute, second=0, microsecond=0)
    close_dt = local_now.replace(hour=store.closes_at.hour, minute=store.closes_at.minute, second=0, microsecond=0)
    if close_dt <= open_dt:
        close_dt += timedelta(days=1)
        if local_now < open_dt:
            previous_open = open_dt - timedelta(days=1)
            previous_close = close_dt - timedelta(days=1)
            if previous_open <= local_now < previous_close:
                return {"is_open": True, "status": "open", "minutes_until_close": max(0, int((previous_close-local_now).total_seconds()//60)), "next_open_at": None}
    if open_dt <= local_now < close_dt:
        return {"is_open": True, "status": "open", "minutes_until_close": max(0, int((close_dt-local_now).total_seconds()//60)), "next_open_at": None}
    next_open = open_dt if local_now < open_dt else open_dt + timedelta(days=1)
    return {"is_open": False, "status": "closed", "minutes_until_close": None, "next_open_at": next_open.isoformat()}


@router.get("/stores/{store_id}/availability")
def store_availability(store_id: uuid.UUID, db: Session = Depends(get_db)):
    store = db.get(Store, store_id)
    if store is None or not store.is_active:
        raise HTTPException(status_code=404, detail="Store not found")
    state = _availability(store, datetime.now(tz=INDIA_TZ))
    return {
        "store_id": store.id,
        **state,
        "delivery_available": bool(state["is_open"] and store.delivery_enabled),
        "pickup_available": bool(state["is_open"] and store.pickup_enabled),
    }
