"""Background auto-dispatch of ready, unassigned GaonOne deliveries.

Only assigns when a verified, active, online rider has a recent GPS fix.
Orders that cannot be matched remain unassigned for later retries/manual recovery.
The existing manual admin auto-assign endpoint remains available.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commerce import Store
from app.services.audit import annotate_delivery_transition
from app.models.orders import Delivery, DeliveryStatus, Order, OrderStatus
from app.models.user import User
from app.services.notifications import enqueue_notification
from app.services.order_transitions import payment_allows_fulfillment, transition_delivery
from app.services.spatial import nearest_eligible_rider

logger = logging.getLogger(__name__)
DEFAULT_RADIUS_KM = 8.0


def dispatch_ready_deliveries(db: Session, limit: int = 25, radius_km: float = DEFAULT_RADIUS_KM) -> dict[str, int]:
    """Claim ready orders with SKIP LOCKED and allocate nearest available riders.

    One DB transaction per assignment; failures do not strand the entire batch.
    """
    matched = 0
    skipped = 0
    seen: set = set()
    for _ in range(limit):
        try:
            # Prevent a tight loop reselecting the same unmatched delivery.
            # Keep candidate ids in memory for this pass; retry on the next tick.
            query = (
                select(Delivery)
                .join(Order, Delivery.order_id == Order.id)
                .where(Delivery.status == DeliveryStatus.UNASSIGNED, Order.status == OrderStatus.READY)
                .order_by(Delivery.updated_at.asc(), Delivery.id.asc())
                .with_for_update(of=Delivery, skip_locked=True)
                .limit(1)
            )
            if seen:
                query = query.where(Delivery.id.not_in(seen))
            delivery = db.scalar(query)
            if delivery is None:
                db.rollback()
                break
            seen.add(delivery.id)
            order = db.get(Order, delivery.order_id)
            store = db.get(Store, order.store_id) if order else None
            if (
                order is None or not payment_allows_fulfillment(order)
                or store is None or store.latitude is None or store.longitude is None
            ):
                skipped += 1
                db.rollback()
                continue
            candidate = nearest_eligible_rider(
                db, store_latitude=float(store.latitude),
                store_longitude=float(store.longitude), max_radius_km=radius_km,
            )
            if candidate is None:
                skipped += 1
                db.rollback()
                continue
            rider_id, _distance = candidate
            rider = db.get(User, rider_id)
            if rider is None:
                skipped += 1
                db.rollback()
                continue
            # Rider is locked by nearest_eligible_rider; repeat the busy check
            # under that lock to prevent two deliveries claiming the same rider.
            active = db.scalar(
                select(Delivery.id).where(
                    Delivery.delivery_partner_id == rider_id,
                    Delivery.status.in_((DeliveryStatus.ASSIGNED, DeliveryStatus.PICKED_UP)),
                ).limit(1)
            )
            if active is not None:
                skipped += 1
                db.rollback()
                continue
            delivery.delivery_partner_id = rider_id
            transition_delivery(delivery, DeliveryStatus.ASSIGNED)
            delivery.assigned_at = datetime.now(timezone.utc)
            annotate_delivery_transition(
                db, delivery, to_status=DeliveryStatus.ASSIGNED.value,
                reason="background_auto_dispatch",
                metadata={"rider_id": str(rider_id), "selection": "nearest_eligible_online_rider"},
            )
            enqueue_notification(
                db, user_id=rider_id, event_type="delivery.task_assigned",
                title="New delivery assigned",
                body=f"Order {order.order_number} is ready for pickup.",
                data={"order_id": str(order.id), "order_number": order.order_number, "delivery_id": str(delivery.id)},
            )
            enqueue_notification(
                db, user_id=order.user_id, event_type="delivery.assigned",
                title="Delivery partner assigned",
                body=f"{rider.full_name or 'Your delivery partner'} is assigned to order {order.order_number}.",
                data={"order_id": str(order.id), "order_number": order.order_number, "delivery_id": str(delivery.id)},
            )
            db.commit()
            matched += 1
        except Exception:
            db.rollback()
            logger.exception("Automatic rider assignment failed")
            skipped += 1
    return {"assigned": matched, "skipped": skipped}
