import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.commerce import Merchant, Store
from app.models.orders import Delivery, Order
from app.models.user import User, UserRole
from app.schemas.delivery_analytics import DeliveryEtaRead, DeliveryPerformanceRead
from app.services.delivery_analytics import delivery_performance, estimate_delivery_eta

router = APIRouter(tags=["Delivery Analytics"])


def _can_view_eta(db: Session, order: Order, delivery: Delivery, user: User) -> bool:
    if user.role == UserRole.ADMIN or order.user_id == user.id:
        return True
    if user.role == UserRole.DELIVERY:
        return delivery.delivery_partner_id == user.id
    if user.role == UserRole.MERCHANT:
        merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
        store = db.get(Store, order.store_id)
        return bool(merchant and store and store.merchant_id == merchant.id)
    return False


@router.get("/orders/{order_id}/eta", response_model=DeliveryEtaRead)
def order_delivery_eta(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    delivery = db.scalar(select(Delivery).where(Delivery.order_id == order.id))
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if not _can_view_eta(db, order, delivery, user):
        raise HTTPException(status_code=403, detail="You cannot view this delivery ETA")
    return estimate_delivery_eta(db, order, delivery)


@router.get("/admin/delivery-performance", response_model=DeliveryPerformanceRead)
def admin_delivery_performance(
    window_days: int = Query(default=30, ge=1, le=180),
    target_minutes: int = Query(default=90, ge=15, le=1440),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    return delivery_performance(db, window_days=window_days, target_minutes=target_minutes)
