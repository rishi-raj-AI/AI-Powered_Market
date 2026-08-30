import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.commerce import Merchant, MerchantStatus, Store
from app.models.orders import Order, OrderStatus

router = APIRouter(tags=["Commerce Intelligence"])


@router.get("/stores/{store_id}/preparation-estimate")
def preparation_estimate(store_id: uuid.UUID, db: Session = Depends(get_db)):
    store = db.get(Store, store_id)
    merchant = db.get(Merchant, store.merchant_id) if store else None
    if store is None or not store.is_active or merchant is None or merchant.status != MerchantStatus.APPROVED:
        raise HTTPException(status_code=404, detail="Store not found")

    completed_states = [OrderStatus.READY, OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED]
    row = db.execute(
        select(
            func.count(Order.id),
            func.avg(func.extract("epoch", Order.updated_at - Order.created_at) / 60.0),
            func.percentile_cont(0.5).within_group(func.extract("epoch", Order.updated_at - Order.created_at) / 60.0),
        ).where(Order.store_id == store_id, Order.status.in_(completed_states))
    ).one()
    samples = int(row[0] or 0)
    average = float(row[1]) if row[1] is not None else None
    median = float(row[2]) if row[2] is not None else None

    if samples >= 5 and median is not None:
        estimate = max(10, min(90, round(median)))
        confidence = "high" if samples >= 20 else "medium"
        basis = "historical_store_median"
    elif samples > 0 and average is not None:
        estimate = max(15, min(90, round(average)))
        confidence = "low"
        basis = "limited_store_history"
    else:
        estimate = 30
        confidence = "low"
        basis = "platform_fallback"

    return {
        "store_id": str(store_id),
        "estimated_preparation_minutes": estimate,
        "confidence": confidence,
        "sample_count": samples,
        "basis": basis,
    }
