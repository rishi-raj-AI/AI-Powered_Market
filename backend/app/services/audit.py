"""Status transition audit trail.

Rows in ``status_transition_events`` are written by database triggers
(``trg_audit_order_status`` and ``trg_audit_delivery_status``, migration 0007).
That is the right place for them: the trigger fires on *any* status update,
including one that application code forgot to log, so the trail cannot be
bypassed.

What a trigger cannot know is who made the change and why. This module fills
that in, by annotating the row the trigger just wrote rather than inserting a
second one — two rows per transition would make the ledger lie about how many
things happened.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orders import Delivery, Order, StatusTransitionEvent

ENTITY_ORDER = "order"
ENTITY_DELIVERY = "delivery"


def annotate_transition(
    db: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    to_status: str,
    actor_user_id: uuid.UUID | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> StatusTransitionEvent | None:
    """Attach actor and reason to the transition the trigger just recorded.

    Must be called after the status change is flushed, so the trigger has run.
    Returns ``None`` when no matching row exists — an annotation is never worth
    failing a business transaction over.
    """
    db.flush()
    event = db.scalar(
        select(StatusTransitionEvent)
        .where(
            StatusTransitionEvent.entity_type == entity_type,
            StatusTransitionEvent.entity_id == entity_id,
            StatusTransitionEvent.to_status == to_status,
        )
        .order_by(StatusTransitionEvent.created_at.desc(), StatusTransitionEvent.id.desc())
        .limit(1)
    )
    if event is None:
        return None
    if actor_user_id is not None:
        event.actor_user_id = actor_user_id
    if reason:
        event.reason = reason[:160]
    if metadata:
        merged = dict(event.event_metadata or {})
        merged.update(metadata)
        event.event_metadata = merged
    return event


def annotate_order_transition(
    db: Session,
    order: Order,
    *,
    to_status: str,
    actor_user_id: uuid.UUID | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> StatusTransitionEvent | None:
    return annotate_transition(
        db,
        entity_type=ENTITY_ORDER,
        entity_id=order.id,
        to_status=to_status,
        actor_user_id=actor_user_id,
        reason=reason,
        metadata=metadata,
    )


def annotate_delivery_transition(
    db: Session,
    delivery: Delivery,
    *,
    to_status: str,
    actor_user_id: uuid.UUID | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> StatusTransitionEvent | None:
    return annotate_transition(
        db,
        entity_type=ENTITY_DELIVERY,
        entity_id=delivery.id,
        to_status=to_status,
        actor_user_id=actor_user_id,
        reason=reason,
        metadata=metadata,
    )
