from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.request_context import request_id
from app.models.integrations import NotificationEvent


def _pending_idempotent_event(db: Session, idempotency_key: str) -> NotificationEvent | None:
    """Return a same-key event already staged in this unit of work.

    SQL queries do not reliably see pending objects when callers use a
    no-autoflush session or when multiple events are staged before the next
    flush. Checking ``Session.new`` keeps idempotency correct inside a single
    business transaction without forcing an early flush of unrelated changes.
    """
    for candidate in db.new:
        if (
            isinstance(candidate, NotificationEvent)
            and candidate.idempotency_key == idempotency_key
        ):
            return candidate
    return None


def enqueue_notification(
    db: Session,
    *,
    user_id: uuid.UUID,
    event_type: str,
    title: str,
    body: str,
    data: dict | None = None,
    idempotency_key: str | None = None,
) -> NotificationEvent:
    if idempotency_key:
        pending = _pending_idempotent_event(db, idempotency_key)
        if pending is not None:
            return pending
        existing = db.scalar(
            select(NotificationEvent).where(NotificationEvent.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing

    event = NotificationEvent(
        user_id=user_id,
        event_type=event_type,
        title=title,
        body=body,
        data=data or {},
        status="pending",
        idempotency_key=idempotency_key,
        request_id=request_id(),
    )
    db.add(event)
    return event
