"""Push delivery for the notification outbox.

A stored NotificationEvent is a durable record that something happened, not
proof that a push was delivered. This module is the only thing that turns one
into the other, and it keeps delivery accounting so a permanently failing event
cannot sit at the head of the queue blocking everything behind it.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.integrations import DeviceRegistration, NotificationEvent

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_NO_DEVICES = "no_devices"
STATUS_IN_APP_ONLY = "in_app_only"
#: Terminal. Repeated delivery attempts failed; the in-app record still stands.
STATUS_DEAD = "dead"

MAX_DELIVERY_ATTEMPTS = 6
#: Backoff per attempt, capped. Keeps a provider outage from becoming a hot loop.
BACKOFF_SECONDS = (30, 120, 600, 1800, 3600, 7200)


def _firebase():
    if not settings.FCM_PROJECT_ID or not settings.FCM_SERVICE_ACCOUNT_JSON_B64:
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging

        if not firebase_admin._apps:
            info = json.loads(base64.b64decode(settings.FCM_SERVICE_ACCOUNT_JSON_B64).decode("utf-8"))
            firebase_admin.initialize_app(credentials.Certificate(info), {"projectId": settings.FCM_PROJECT_ID})
        return messaging
    except Exception:
        logger.exception("FCM initialization failed")
        return None


def _backoff(attempt_count: int) -> datetime:
    index = min(max(attempt_count - 1, 0), len(BACKOFF_SECONDS) - 1)
    return datetime.now(timezone.utc) + timedelta(seconds=BACKOFF_SECONDS[index])


def _defer(event: NotificationEvent, message: str) -> None:
    """Keep the event pending with backoff, or retire it after enough tries."""
    event.attempt_count += 1
    event.last_error = message[:300]
    if event.attempt_count >= MAX_DELIVERY_ATTEMPTS:
        event.status = STATUS_DEAD
        event.next_attempt_at = None
        logger.warning(
            "Notification retired after %s attempts event_id=%s type=%s: %s",
            event.attempt_count,
            event.id,
            event.event_type,
            message,
        )
    else:
        event.status = STATUS_PENDING
        event.next_attempt_at = _backoff(event.attempt_count)


def deliver_event(db: Session, event: NotificationEvent) -> int:
    messaging = _firebase()
    if messaging is None:
        if settings.FCM_PROJECT_ID:
            # Configured but unusable: this is a real failure worth retrying.
            _defer(event, "FCM is configured but could not be initialised")
            return 0
        # Push is not configured at all. The in-app record is the delivery.
        event.status = STATUS_IN_APP_ONLY
        event.next_attempt_at = None
        return 0

    devices = db.scalars(
        select(DeviceRegistration).where(
            DeviceRegistration.user_id == event.user_id,
            DeviceRegistration.is_active.is_(True),
        )
    ).all()
    if not devices:
        event.status = STATUS_NO_DEVICES
        event.next_attempt_at = None
        return 0

    sent = 0
    invalid: list[str] = []
    last_error = ""
    data = {str(k): str(v) for k, v in (event.data or {}).items() if v is not None}
    for device in devices:
        try:
            messaging.send(
                messaging.Message(
                    notification=messaging.Notification(title=event.title, body=event.body),
                    data=data,
                    token=device.token,
                )
            )
            sent += 1
        except Exception as exc:  # provider errors are per-device
            text = str(exc).lower()
            if "registration-token-not-registered" in text or "not found" in text or "unregistered" in text:
                invalid.append(device.token)
            else:
                last_error = str(exc)
                logger.warning("FCM send failed for event %s: %s", event.id, exc)

    for device in devices:
        if device.token in invalid:
            device.is_active = False

    if sent:
        event.status = STATUS_SENT
        event.sent_at = datetime.now(timezone.utc)
        event.next_attempt_at = None
        event.last_error = None
    elif invalid and not last_error:
        # Every device token was stale; there is nobody left to deliver to.
        event.status = STATUS_NO_DEVICES
        event.next_attempt_at = None
    else:
        _defer(event, last_error or "No push could be delivered to any registered device")
    return sent


def due_events(db: Session, limit: int = 100) -> list[NotificationEvent]:
    now = datetime.now(timezone.utc)
    return list(
        db.scalars(
            select(NotificationEvent)
            .where(
                NotificationEvent.status == STATUS_PENDING,
                or_(
                    NotificationEvent.next_attempt_at.is_(None),
                    NotificationEvent.next_attempt_at <= now,
                ),
            )
            .order_by(NotificationEvent.created_at)
            .limit(limit)
        ).all()
    )


def flush_pending(db: Session, limit: int = 100) -> dict[str, int]:
    events = due_events(db, limit=limit)
    delivered = 0
    for event in events:
        delivered += deliver_event(db, event)
    db.commit()
    return {"events": len(events), "pushes": delivered}
