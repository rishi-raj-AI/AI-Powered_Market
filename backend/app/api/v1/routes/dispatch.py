import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.commerce import Store
from app.models.dispatch import RiderPresence
from app.models.orders import Delivery, DeliveryStatus, Order, OrderStatus
from app.models.user import User, UserRole
from app.schemas.dispatch import AutoDispatchRead, AutoDispatchRequest, RiderPresenceRead, RiderPresenceUpdate
from app.services.notifications import enqueue_notification
from app.services.spatial import best_eligible_rider

router = APIRouter(tags=["Dispatch"])


@router.put("/delivery/presence", response_model=RiderPresenceRead)
def update_rider_presence(
    payload: RiderPresenceUpdate,
    db: Session = Depends(get_db),
    rider: User = Depends(require_roles(UserRole.DELIVERY)),
):
    now = datetime.now(timezone.utc)
    presence = db.get(RiderPresence, rider.id)
    if presence is None:
        presence = RiderPresence(rider_id=rider.id)
        db.add(presence)
    presence.latitude = payload.latitude
    presence.longitude = payload.longitude
    presence.is_online = payload.is_online
    presence.last_seen_at = now
    db.commit()
    db.refresh(presence)
    return presence


@router.get("/delivery/presence", response_model=RiderPresenceRead | None)
def my_rider_presence(
    db: Session = Depends(get_db),
    rider: User = Depends(require_roles(UserRole.DELIVERY)),
):
    return db.get(RiderPresence, rider.id)


@router.post("/admin/deliveries/{delivery_id}/auto-assign", response_model=AutoDispatchRead)
def auto_assign_delivery(
    delivery_id: uuid.UUID,
    payload: AutoDispatchRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    delivery = db.scalar(select(Delivery).where(Delivery.id == delivery_id).with_for_update())
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    order = db.scalar(select(Order).where(Order.id == delivery.order_id).with_for_update())
    if order is None:
        raise HTTPException(status_code=409, detail="Delivery order is missing")
    if delivery.status != DeliveryStatus.UNASSIGNED or order.status != OrderStatus.READY:
        raise HTTPException(status_code=409, detail="Delivery is no longer available for dispatch")

    store = db.get(Store, order.store_id)
    if store is None or store.latitude is None or store.longitude is None:
        raise HTTPException(status_code=409, detail="Store location is required for automatic dispatch")

    candidate = best_eligible_rider(
        db,
        store_id=store.id,
        store_latitude=float(store.latitude),
        store_longitude=float(store.longitude),
        max_radius_km=payload.max_radius_km,
        allow_batch=payload.allow_batch,
    )
    if candidate is None:
        raise HTTPException(status_code=409, detail="No eligible delivery partner is currently available")

    rider_id, distance_km, active_tasks, score = candidate
    rider = db.get(User, rider_id)
    if rider is None:
        raise HTTPException(status_code=409, detail="Selected delivery partner is no longer available")

    now = datetime.now(timezone.utc)
    delivery.delivery_partner_id = rider.id
    delivery.status = DeliveryStatus.ASSIGNED
    delivery.assigned_at = now

    enqueue_notification(
        db,
        user_id=order.user_id,
        event_type="delivery.assigned",
        title="Delivery partner assigned",
        body=f"{rider.full_name or 'Your delivery partner'} is assigned to order {order.order_number}.",
        data={
            "order_id": str(order.id),
            "order_number": order.order_number,
            "delivery_id": str(delivery.id),
            "batched": active_tasks > 0,
        },
        idempotency_key=f"delivery:{delivery.id}:assigned:customer:rider:{rider.id}",
    )
    enqueue_notification(
        db,
        user_id=rider.id,
        event_type="delivery.task_assigned",
        title="New delivery assigned",
        body=f"Order {order.order_number} is ready for pickup.",
        data={
            "order_id": str(order.id),
            "order_number": order.order_number,
            "delivery_id": str(delivery.id),
            "batched": active_tasks > 0,
        },
        idempotency_key=f"delivery:{delivery.id}:assigned:rider:{rider.id}",
    )

    db.commit()
    return AutoDispatchRead(
        delivery_id=delivery.id,
        order_id=order.id,
        rider_id=rider.id,
        rider_name=rider.full_name,
        distance_km=round(distance_km, 2),
        assigned_at=now,
        score=round(score, 3),
        active_tasks=active_tasks,
        batched=active_tasks > 0,
    )
