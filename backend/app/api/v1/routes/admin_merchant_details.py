import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_capability
from app.core.capabilities import Capability
from app.models.commerce import Merchant, Store, StoreProduct
from app.models.orders import Order
from app.models.user import User
from app.models.integrations import NotificationEvent, DeviceRegistration

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/merchants/{merchant_id}/details")
def merchant_details(
    merchant_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_capability(Capability.MERCHANT_READ)),
):
    merchant = db.get(Merchant, merchant_id)
    if merchant is None:
        raise HTTPException(status_code=404, detail="Merchant not found")
    owner = db.get(User, merchant.owner_user_id)
    stores = db.scalars(select(Store).where(Store.merchant_id == merchant.id).order_by(Store.name)).all()
    result = []
    for store in stores:
        order_count = db.scalar(select(func.count(Order.id)).where(Order.store_id == store.id)) or 0
        listing_count = db.scalar(select(func.count(StoreProduct.id)).where(StoreProduct.store_id == store.id)) or 0
        result.append({
            "id": str(store.id), "name": store.name, "phone": store.phone,
            "landmark": store.landmark, "is_active": store.is_active,
            "delivery_enabled": store.delivery_enabled,
            "orders": order_count, "listings": listing_count,
        })
    return {
        "merchant_id": str(merchant.id), "business_name": merchant.business_name,
        "status": merchant.status.value, "gstin": merchant.gstin,
        "created_at": merchant.created_at,
        "owner": {"id": str(owner.id), "name": owner.full_name, "phone": owner.phone,
                  "is_active": owner.is_active} if owner else None,
        "stores": result,
    }

@router.get("/notifications/health")
def notification_health(
    db: Session = Depends(get_db),
    _: User = Depends(require_capability(Capability.NOTIFICATION_OPERATIONS)),
):
    """Operational counts only: no device tokens or customer message bodies."""
    rows = db.execute(
        select(NotificationEvent.event_type, NotificationEvent.status, func.count(NotificationEvent.id))
        .where(NotificationEvent.event_type.in_(
            ("merchant.order_received", "merchant.new_order", "delivery.task_assigned", "delivery.assigned")
        ))
        .group_by(NotificationEvent.event_type, NotificationEvent.status)
    ).all()
    totals: dict[str, dict[str, int]] = {}
    for event_type, status, count in rows:
        totals.setdefault(event_type, {})[status] = count
    active_devices = db.scalar(
        select(func.count(DeviceRegistration.id)).where(DeviceRegistration.is_active.is_(True))
    ) or 0
    return {"event_status_counts": totals, "active_devices": active_devices}
