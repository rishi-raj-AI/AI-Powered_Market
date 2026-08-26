from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from app.api.deps import get_db, require_roles
from app.models.commerce import Store
from app.models.geography import Address
from app.models.orders import Delivery, DeliveryStatus, Order, OrderStatus
from app.models.user import User, UserRole
from app.schemas.orders import DeliveryTaskRead

router = APIRouter(prefix="/delivery/tasks", tags=["Delivery Tasks"])


def _task(db: Session, delivery: Delivery) -> DeliveryTaskRead | None:
    order = db.get(Order, delivery.order_id)
    if order is None:
        return None
    store = db.get(Store, order.store_id)
    address = db.get(Address, order.address_id)
    if store is None or address is None:
        return None
    return DeliveryTaskRead(
        id=delivery.id,
        order_id=order.id,
        order_number=order.order_number,
        status=delivery.status,
        payment_method=order.payment_method,
        payment_status=order.payment_status,
        total=order.total,
        store_name=store.name,
        store_phone=store.phone,
        store_landmark=store.landmark,
        store_latitude=float(store.latitude) if store.latitude is not None else None,
        store_longitude=float(store.longitude) if store.longitude is not None else None,
        recipient_name=address.recipient_name,
        recipient_phone=address.phone,
        house_details=address.house_details,
        customer_landmark=address.landmark,
        customer_directions=address.directions,
        customer_latitude=address.latitude,
        customer_longitude=address.longitude,
    )


@router.get("/available", response_model=list[DeliveryTaskRead])
def available_tasks(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.DELIVERY, UserRole.ADMIN)),
):
    deliveries = db.scalars(
        select(Delivery)
        .join(Order, Delivery.order_id == Order.id)
        .where(
            Delivery.status == DeliveryStatus.UNASSIGNED,
            Order.status == OrderStatus.READY,
        )
        .order_by(Delivery.updated_at)
    ).all()
    return [task for delivery in deliveries if (task := _task(db, delivery)) is not None]


@router.get("/me", response_model=list[DeliveryTaskRead])
def my_tasks(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.DELIVERY, UserRole.ADMIN)),
):
    stmt = select(Delivery).order_by(Delivery.updated_at.desc())
    if user.role != UserRole.ADMIN:
        stmt = stmt.where(Delivery.delivery_partner_id == user.id)
    deliveries = db.scalars(stmt).all()
    return [task for delivery in deliveries if (task := _task(db, delivery)) is not None]
