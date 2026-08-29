import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.commerce import Merchant, Store
from app.models.geography import Address
from app.models.orders import Delivery, DeliveryLocation, DeliveryStatus, Order
from app.models.user import User, UserRole
from app.schemas.tracking import (
    DeliveryLocationCreate,
    DeliveryLocationRead,
    OrderTrackingRead,
    RouteRead,
    TrackingPoint,
)
from app.services.maps import compute_route, maps_enabled

router = APIRouter(tags=["Live Tracking"])
ACTIVE_TRACKING_STATUSES = {DeliveryStatus.ASSIGNED, DeliveryStatus.PICKED_UP}
MIN_LOCATION_INTERVAL_SECONDS = 5


def _can_view_tracking(db: Session, order: Order, delivery: Delivery | None, user: User) -> bool:
    if user.role == UserRole.ADMIN or order.user_id == user.id:
        return True
    if delivery is not None and delivery.delivery_partner_id == user.id:
        return True
    if user.role == UserRole.MERCHANT:
        merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
        store = db.get(Store, order.store_id)
        return merchant is not None and store is not None and store.merchant_id == merchant.id
    return False


def _latest_location(db: Session, delivery_id: uuid.UUID) -> DeliveryLocation | None:
    return db.scalar(
        select(DeliveryLocation)
        .where(DeliveryLocation.delivery_id == delivery_id)
        .order_by(DeliveryLocation.recorded_at.desc())
        .limit(1)
    )


def _location_read(location: DeliveryLocation) -> DeliveryLocationRead:
    return DeliveryLocationRead(
        id=location.id,
        delivery_id=location.delivery_id,
        latitude=location.latitude,
        longitude=location.longitude,
        accuracy_m=location.accuracy_m,
        heading_deg=location.heading_deg,
        speed_mps=location.speed_mps,
        recorded_at=location.recorded_at,
    )


def _tracking_context(db: Session, order_id: uuid.UUID, user: User):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    delivery = db.scalar(select(Delivery).where(Delivery.order_id == order.id))
    if not _can_view_tracking(db, order, delivery, user):
        raise HTTPException(status_code=403, detail="You cannot view tracking for this order")
    store = db.get(Store, order.store_id)
    address = db.get(Address, order.address_id)
    return order, delivery, store, address


@router.post("/delivery/{delivery_id}/location", response_model=DeliveryLocationRead, status_code=201)
def record_delivery_location(
    delivery_id: uuid.UUID,
    payload: DeliveryLocationCreate,
    db: Session = Depends(get_db),
    rider: User = Depends(require_roles(UserRole.DELIVERY)),
):
    delivery = db.get(Delivery, delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if delivery.delivery_partner_id != rider.id:
        raise HTTPException(status_code=403, detail="Delivery is not assigned to you")
    if delivery.status not in ACTIVE_TRACKING_STATUSES:
        raise HTTPException(status_code=409, detail="Live location is only accepted during an active delivery")

    now = datetime.now(timezone.utc)
    recorded_at = payload.recorded_at.astimezone(timezone.utc)
    if recorded_at > now + timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="Location timestamp is too far in the future")
    if recorded_at < now - timedelta(minutes=30):
        raise HTTPException(status_code=422, detail="Location timestamp is too old")

    latest = _latest_location(db, delivery.id)
    if latest is not None:
        latest_recorded_at = latest.recorded_at.astimezone(timezone.utc)
        if recorded_at <= latest_recorded_at:
            raise HTTPException(status_code=409, detail="Location timestamp must be newer than the previous update")
        if (recorded_at - latest_recorded_at).total_seconds() < MIN_LOCATION_INTERVAL_SECONDS:
            raise HTTPException(status_code=429, detail="Location updates are limited to one every 5 seconds")

    location = DeliveryLocation(
        delivery_id=delivery.id,
        delivery_partner_id=rider.id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_m=payload.accuracy_m,
        heading_deg=payload.heading_deg,
        speed_mps=payload.speed_mps,
        recorded_at=recorded_at,
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return _location_read(location)


@router.get("/orders/{order_id}/tracking", response_model=OrderTrackingRead)
def order_tracking(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order, delivery, store, address = _tracking_context(db, order_id, user)
    active = delivery is not None and delivery.status in ACTIVE_TRACKING_STATUSES
    latest = _latest_location(db, delivery.id) if delivery is not None and active else None
    age_seconds = None
    if latest is not None:
        age_seconds = max(0, int((datetime.now(timezone.utc) - latest.recorded_at).total_seconds()))

    return OrderTrackingRead(
        order_id=order.id,
        order_number=order.order_number,
        order_status=order.status,
        delivery_id=delivery.id if delivery else None,
        delivery_status=delivery.status if delivery else None,
        tracking_active=active,
        store=TrackingPoint(
            latitude=float(store.latitude) if store and store.latitude is not None else None,
            longitude=float(store.longitude) if store and store.longitude is not None else None,
            label=store.name if store else None,
        ),
        customer=TrackingPoint(
            latitude=address.latitude if address else None,
            longitude=address.longitude if address else None,
            label=address.landmark if address else None,
        ),
        rider=_location_read(latest) if latest else None,
        rider_location_age_seconds=age_seconds,
    )


@router.get("/orders/{order_id}/route", response_model=RouteRead)
def order_route(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order, delivery, store, address = _tracking_context(db, order_id, user)
    latest = None
    if delivery is not None and delivery.status in ACTIVE_TRACKING_STATUSES:
        latest = _latest_location(db, delivery.id)

    origin = TrackingPoint(
        latitude=latest.latitude if latest else (float(store.latitude) if store and store.latitude is not None else None),
        longitude=latest.longitude if latest else (float(store.longitude) if store and store.longitude is not None else None),
        label="Delivery partner" if latest else (store.name if store else "Store"),
    )
    destination = TrackingPoint(
        latitude=address.latitude if address else None,
        longitude=address.longitude if address else None,
        label=address.landmark if address else "Delivery address",
    )

    if (
        origin.latitude is None
        or origin.longitude is None
        or destination.latitude is None
        or destination.longitude is None
        or not maps_enabled()
    ):
        return RouteRead(available=False, provider="none", origin=origin, destination=destination)

    result = compute_route(origin.latitude, origin.longitude, destination.latitude, destination.longitude)
    if result is None:
        return RouteRead(available=False, provider="google", origin=origin, destination=destination)
    return RouteRead(
        available=True,
        provider="google",
        origin=origin,
        destination=destination,
        distance_meters=result.distance_meters,
        duration_seconds=result.duration_seconds,
        encoded_polyline=result.encoded_polyline,
    )
