from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.integrations import NotificationEvent


def enqueue_notification(
    db: Session,
    *,
    user_id: uuid.UUID,
    event_type: str,
    title: str,
    body: str,
    data: dict | None = None,
) -> NotificationEvent:
    event = NotificationEvent(
        user_id=user_id,
        event_type=event_type,
        title=title,
        body=body,
        data=data or {},
        status="pending",
    )
    db.add(event)
    return event
