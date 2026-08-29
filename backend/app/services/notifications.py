from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.request_context import request_id
from app.models.integrations import NotificationEvent


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
