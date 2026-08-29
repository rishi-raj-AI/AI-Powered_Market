from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.commerce import Merchant, Store
from app.models.user import User, UserRole
from app.services.demand_forecast import forecast_store_demand

router = APIRouter(prefix="/merchant", tags=["Merchant Intelligence"])


def _require_store_access(db: Session, store_id: uuid.UUID, user: User) -> Store:
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    if user.role == UserRole.ADMIN:
        return store
    merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
    if merchant is None or store.merchant_id != merchant.id:
        raise HTTPException(status_code=403, detail="Store does not belong to your merchant account")
    return store


@router.get("/stores/{store_id}/demand-forecast")
def store_demand_forecast(
    store_id: uuid.UUID,
    window_days: int = Query(default=28, ge=7, le=180),
    horizon_days: int = Query(default=7, ge=1, le=30),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
) -> dict:
    _require_store_access(db, store_id, user)
    return forecast_store_demand(
        db,
        store_id,
        window_days=window_days,
        horizon_days=horizon_days,
    )
