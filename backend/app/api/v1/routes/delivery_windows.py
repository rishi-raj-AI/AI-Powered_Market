from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.commerce import Merchant, MerchantStatus, Store

router = APIRouter(tags=["Fulfillment"])
INDIA_TZ = ZoneInfo("Asia/Kolkata")


class FulfillmentWindowRead(BaseModel):
    start_at: datetime
    end_at: datetime
    mode: str


def _ceil_half_hour(value: datetime) -> datetime:
    value = value.replace(second=0, microsecond=0)
    minute = 0 if value.minute == 0 else 30 if value.minute <= 30 else 0
    if value.minute > 30:
        value += timedelta(hours=1)
    return value.replace(minute=minute)


def _generate_windows(now: datetime, *, days: int = 3, slot_minutes: int = 60) -> list[tuple[datetime, datetime]]:
    local_now = now.astimezone(INDIA_TZ)
    cursor = _ceil_half_hour(local_now + timedelta(minutes=45))
    end = local_now + timedelta(days=days)
    slots: list[tuple[datetime, datetime]] = []
    while cursor < end and len(slots) < 24:
        slot_end = cursor + timedelta(minutes=slot_minutes)
        if 7 <= cursor.hour < 21 and slot_end.hour <= 22:
            slots.append((cursor, slot_end))
        cursor += timedelta(minutes=slot_minutes)
    return slots


@router.get('/stores/{store_id}/fulfillment-windows', response_model=list[FulfillmentWindowRead])
def fulfillment_windows(
    store_id: uuid.UUID,
    mode: str = Query(default='delivery', pattern='^(delivery|pickup)$'),
    days: int = Query(default=3, ge=1, le=7),
    db: Session = Depends(get_db),
):
    store = db.scalar(
        select(Store)
        .join(Merchant, Merchant.id == Store.merchant_id)
        .where(Store.id == store_id, Store.is_active.is_(True), Merchant.status == MerchantStatus.APPROVED)
    )
    if store is None:
        raise HTTPException(status_code=404, detail='Store not found')
    if mode == 'delivery' and not store.delivery_enabled:
        return []
    if mode == 'pickup' and not store.pickup_enabled:
        return []

    slots = _generate_windows(datetime.now(INDIA_TZ), days=days)
    return [FulfillmentWindowRead(start_at=start, end_at=end, mode=mode) for start, end in slots]
