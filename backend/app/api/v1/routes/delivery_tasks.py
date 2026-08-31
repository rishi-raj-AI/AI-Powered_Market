"""Delivery task listings for riders.

Least privilege by assignment state. An unassigned task is an *offer*: a rider
needs to know where to collect, roughly how far the drop is, what the order is
worth and whether cash is involved. They do not need — and before this, every
rider on the platform could read — the waiting customer's name, phone, house
details and exact coordinates for every open order.
"""

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.commerce import Store
from app.models.geography import Address, Village
from app.models.orders import Delivery, DeliveryStatus, Order, OrderItem, OrderStatus
from app.models.user import User, UserRole
from app.schemas.orders import DeliveryTaskOfferRead, DeliveryTaskRead

router = APIRouter(prefix="/delivery/tasks", tags=["Delivery Tasks"])
ACTIVE_DELIVERY_STATUSES = {DeliveryStatus.ASSIGNED, DeliveryStatus.PICKED_UP}


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _offer(db: Session, delivery: Delivery) -> DeliveryTaskOfferRead | None:
    order = db.get(Order, delivery.order_id)
    if order is None:
        return None
    store = db.get(Store, order.store_id)
    address = db.get(Address, order.address_id)
    if store is None or address is None:
        return None

    item_count = (
        db.scalar(select(func.count()).select_from(OrderItem).where(OrderItem.order_id == order.id)) or 0
    )

    # Coarse locality label rather than the customer's landmark, which is
    # effectively their address.
    village = db.get(Village, address.village_id) if address.village_id else None
    dropoff_area = village.name if village else None

    distance = None
    if (
        store.latitude is not None
        and store.longitude is not None
        and address.latitude is not None
        and address.longitude is not None
    ):
        # Rounded to the nearest half kilometre: useful for judging the job,
        # useless for locating a household.
        exact = _distance_km(
            float(store.latitude), float(store.longitude), address.latitude, address.longitude
        )
        distance = round(exact * 2) / 2

    return DeliveryTaskOfferRead(
        id=delivery.id,
        order_id=order.id,
        order_number=order.order_number,
        status=delivery.status,
        payment_method=order.payment_method,
        payment_status=order.payment_status,
        total=order.total,
        item_count=item_count,
        store_name=store.name,
        store_landmark=store.landmark,
        store_latitude=float(store.latitude) if store.latitude is not None else None,
        store_longitude=float(store.longitude) if store.longitude is not None else None,
        dropoff_area=dropoff_area,
        dropoff_distance_km=distance,
    )


def _task(db: Session, delivery: Delivery) -> DeliveryTaskRead | None:
    """Full delivery detail. Only ever returned for an assigned delivery."""
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


@router.get("/available", response_model=list[DeliveryTaskOfferRead])
def available_tasks(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.DELIVERY, UserRole.ADMIN)),
):
    """Open delivery offers. Customer identity is withheld until assignment."""
    if user.role == UserRole.DELIVERY:
        active = db.scalar(
            select(Delivery.id)
            .where(
                Delivery.delivery_partner_id == user.id,
                Delivery.status.in_(ACTIVE_DELIVERY_STATUSES),
            )
            .limit(1)
        )
        if active is not None:
            return []
    deliveries = db.scalars(
        select(Delivery)
        .join(Order, Delivery.order_id == Order.id)
        .where(
            Delivery.status == DeliveryStatus.UNASSIGNED,
            Order.status == OrderStatus.READY,
        )
        .order_by(Delivery.updated_at)
        .limit(limit)
    ).all()
    return [offer for delivery in deliveries if (offer := _offer(db, delivery)) is not None]


@router.get("/me", response_model=list[DeliveryTaskRead])
def my_tasks(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.DELIVERY, UserRole.ADMIN)),
):
    """Deliveries assigned to the caller, with the detail needed to deliver."""
    stmt = select(Delivery).order_by(Delivery.updated_at.desc()).limit(limit)
    if user.role != UserRole.ADMIN:
        stmt = stmt.where(Delivery.delivery_partner_id == user.id)
    deliveries = db.scalars(stmt).all()
    return [task for delivery in deliveries if (task := _task(db, delivery)) is not None]
