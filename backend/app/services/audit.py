"""Status transition audit trail.

``StatusTransitionEvent`` existed as a table and a read endpoint but nothing
ever wrote to it, so ``GET /orders/{id}/events`` always returned an empty list.
Every backend-owned state change should be explainable after the fact,
especially the ones with financial consequences.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.orders import Delivery, Order, StatusTransitionEvent

ENTITY_ORDER = "order"
ENTITY_DELIVERY = "delivery"
ENTITY_PAYMENT = "payment"


def record_transition(
    db: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    from_status: str,
    to_status: str,
    order_id: uuid.UUID | None = None,
    delivery_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> StatusTransitionEvent:
    """Append one transition to the audit trail within the caller's transaction."""
    event = StatusTransitionEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        order_id=order_id,
        delivery_id=delivery_id,
        actor_user_id=actor_user_id,
        from_status=from_status,
        to_status=to_status,
        reason=reason[:160] if reason else None,
        event_metadata=metadata or {},
    )
    db.add(event)
    return event


def record_order_transition(
    db: Session,
    order: Order,
    *,
    from_status: str,
    to_status: str,
    actor_user_id: uuid.UUID | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> StatusTransitionEvent:
    return record_transition(
        db,
        entity_type=ENTITY_ORDER,
        entity_id=order.id,
        order_id=order.id,
        from_status=from_status,
        to_status=to_status,
        actor_user_id=actor_user_id,
        reason=reason,
        metadata=metadata,
    )


def record_delivery_transition(
    db: Session,
    delivery: Delivery,
    *,
    from_status: str,
    to_status: str,
    actor_user_id: uuid.UUID | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> StatusTransitionEvent:
    return record_transition(
        db,
        entity_type=ENTITY_DELIVERY,
        entity_id=delivery.id,
        order_id=delivery.order_id,
        delivery_id=delivery.id,
        from_status=from_status,
        to_status=to_status,
        actor_user_id=actor_user_id,
        reason=reason,
        metadata=metadata,
    )
