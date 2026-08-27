from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.commerce import Merchant, MerchantStatus, Store, StoreProduct
from app.models.geography import Village
from app.models.orders import Delivery, DeliveryStatus, Order, OrderStatus, PaymentStatus
from app.models.user import User, UserRole

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/overview")
def admin_overview(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> dict:
    user_count = db.scalar(select(func.count()).select_from(User)) or 0
    village_count = db.scalar(
        select(func.count()).select_from(Village).where(Village.is_active.is_(True))
    ) or 0
    active_store_count = db.scalar(
        select(func.count()).select_from(Store).where(Store.is_active.is_(True))
    ) or 0
    pending_merchants = db.scalar(
        select(func.count()).select_from(Merchant).where(Merchant.status == MerchantStatus.PENDING)
    ) or 0
    approved_merchants = db.scalar(
        select(func.count()).select_from(Merchant).where(Merchant.status == MerchantStatus.APPROVED)
    ) or 0
    suspended_merchants = db.scalar(
        select(func.count()).select_from(Merchant).where(Merchant.status == MerchantStatus.SUSPENDED)
    ) or 0
    total_orders = db.scalar(select(func.count()).select_from(Order)) or 0
    paid_gmv = db.scalar(
        select(func.coalesce(func.sum(Order.total), 0)).where(Order.payment_status == PaymentStatus.PAID)
    ) or Decimal("0")
    gross_order_value = db.scalar(
        select(func.coalesce(func.sum(Order.total), 0)).where(Order.status != OrderStatus.CANCELLED)
    ) or Decimal("0")
    low_stock = db.scalar(
        select(func.count())
        .select_from(StoreProduct)
        .where(StoreProduct.stock_quantity <= 5, StoreProduct.is_available.is_(True))
    ) or 0
    ready_unassigned = db.scalar(
        select(func.count())
        .select_from(Delivery)
        .join(Order, Delivery.order_id == Order.id)
        .where(Delivery.status == DeliveryStatus.UNASSIGNED, Order.status == OrderStatus.READY)
    ) or 0

    grouped = db.execute(select(Order.status, func.count(Order.id)).group_by(Order.status)).all()
    orders_by_status = {order_status.value: count for order_status, count in grouped}
    for order_status in OrderStatus:
        orders_by_status.setdefault(order_status.value, 0)

    return {
        "users": user_count,
        "villages": village_count,
        "active_stores": active_store_count,
        "merchants": {
            "pending": pending_merchants,
            "approved": approved_merchants,
            "suspended": suspended_merchants,
        },
        "orders": {
            "total": total_orders,
            "by_status": orders_by_status,
        },
        "operations": {
            "low_stock_listings": low_stock,
            "ready_unassigned_deliveries": ready_unassigned,
        },
        "paid_gmv": str(paid_gmv),
        "gross_order_value": str(gross_order_value),
    }
