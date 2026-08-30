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
_STALE_LOCK = timedelta(minutes=5)
_MAX_BACKOFF_SECONDS = 3600


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


def _retry_delay(attempts: int) -> timedelta:
    seconds = min(_MAX_BACKOFF_SECONDS, 15 * (2 ** max(0, min(attempts - 1, 8))))
    return timedelta(seconds=seconds)


def deliver_event(db: Session, event: NotificationEvent) -> int:
    now = datetime.now(timezone.utc)
    messaging = _firebase()
    if messaging is None:
        if settings.FCM_PROJECT_ID:
            event.status = "failed"
            event.last_error = "FCM provider unavailable"
            event.next_attempt_at = now + _retry_delay(event.attempts)
        else:
            event.status = "in_app_only"
            event.last_error = None
            event.next_attempt_at = None
        event.locked_at = None
        return 0

    devices = db.scalars(
        select(DeviceRegistration).where(
            DeviceRegistration.user_id == event.user_id,
            DeviceRegistration.is_active.is_(True),
        )
    ).all()
    if not devices:
        event.status = "no_devices"
        event.last_error = None
        event.next_attempt_at = None
        event.locked_at = None
        return 0

    sent = 0
    invalid: list[str] = []
    transient_errors: list[str] = []
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
        except Exception as exc:
            text = str(exc).lower()
            if "registration-token-not-registered" in text or "not found" in text or "unregistered" in text:
                invalid.append(device.token)
            else:
                transient_errors.append(str(exc)[:500])
                logger.warning("FCM send failed for event %s: %s", event.id, exc)

    for device in devices:
        if device.token in invalid:
            device.is_active = False

    event.locked_at = None
    if transient_errors:
        event.status = "failed"
        event.last_error = "; ".join(transient_errors)[:2000]
        event.next_attempt_at = now + _retry_delay(event.attempts)
    elif sent:
        event.status = "sent"
        event.sent_at = now
        event.last_error = None
        event.next_attempt_at = None
    else:
        event.status = "no_devices"
        event.last_error = None
        event.next_attempt_at = None
    return sent


def _claim_pending(db: Session, limit: int, *, event_type: str | None = None) -> list[NotificationEvent]:
    now = datetime.now(timezone.utc)
    stale_before = now - _STALE_LOCK
    eligibility = or_(
        NotificationEvent.status == "pending",
        (NotificationEvent.status == "failed")
        & or_(NotificationEvent.next_attempt_at.is_(None), NotificationEvent.next_attempt_at <= now),
        (NotificationEvent.status == "processing")
        & NotificationEvent.locked_at.is_not(None)
        & (NotificationEvent.locked_at <= stale_before),
    )
    statement = select(NotificationEvent).where(eligibility)
    if event_type is not None:
        statement = statement.where(NotificationEvent.event_type == event_type)
    events = db.scalars(
        statement.order_by(NotificationEvent.created_at).with_for_update(skip_locked=True).limit(limit)
    ).all()
    for event in events:
        event.status = "processing"
        event.locked_at = now
        event.attempts += 1
    db.commit()
    return events


def flush_pending(db: Session, limit: int = 100) -> dict[str, int]:
    events = _claim_pending(db, limit)
    delivered = 0
    failed = 0
    for event in events:
        current = db.get(NotificationEvent, event.id)
        if current is None or current.status != "processing":
            continue
        try:
            delivered += deliver_event(db, current)
            if current.status == "failed":
                failed += 1
            db.commit()
        except Exception as exc:
            db.rollback()
            current = db.get(NotificationEvent, event.id)
            if current is not None:
                now = datetime.now(timezone.utc)
                current.status = "failed"
                current.locked_at = None
                current.last_error = str(exc)[:2000]
                current.next_attempt_at = now + _retry_delay(max(current.attempts, 1))
                db.commit()
            failed += 1
            logger.exception("Notification outbox delivery failed for event %s", event.id)
    return {"events": len(events), "pushes": delivered, "failed": failed}
