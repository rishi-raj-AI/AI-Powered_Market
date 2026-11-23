"""Replay durable Razorpay webhooks without starving newer events.

A provider may still report an authorized payment after sending a signed
capture event. Persist a bounded exponential retry schedule rather than
reselecting the oldest unprocessed rows on every worker tick. Never drop an
unresolved financial event merely because it has been retried many times.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.v1.routes.payment_hardening import _process_event
from app.models.integrations import PaymentWebhookEvent

logger = logging.getLogger(__name__)

MAX_RETRY_SECONDS = 3600
BASE_RETRY_SECONDS = 60


def _schedule_retry(db: Session, event_id: UUID) -> None:
    """Persist backoff in a new transaction after any provider/DB rollback."""
    event = db.scalar(
        select(PaymentWebhookEvent)
        .where(PaymentWebhookEvent.id == event_id)
        .with_for_update(skip_locked=True)
    )
    if event is None or event.processed_at is not None:
        db.rollback()
        return
    event.attempt_count += 1
    delay = min(MAX_RETRY_SECONDS, BASE_RETRY_SECONDS * (2 ** min(event.attempt_count - 1, 6)))
    event.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
    db.commit()


def replay_pending_payment_webhooks(
    db: Session, *, limit: int = 25, min_age_seconds: int = 60,
) -> dict[str, int]:
    if limit < 1 or min_age_seconds < 0:
        raise ValueError("Invalid webhook replay limits")
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=min_age_seconds)
    ids = db.scalars(
        select(PaymentWebhookEvent.id)
        .where(
            PaymentWebhookEvent.provider == "razorpay",
            PaymentWebhookEvent.processed_at.is_(None),
            PaymentWebhookEvent.created_at <= cutoff,
            or_(
                PaymentWebhookEvent.next_attempt_at.is_(None),
                PaymentWebhookEvent.next_attempt_at <= now,
            ),
        )
        .order_by(PaymentWebhookEvent.created_at, PaymentWebhookEvent.id)
        .limit(limit)
    ).all()
    result = {"considered": len(ids), "processed": 0, "deferred": 0}
    for event_id in ids:
        try:
            event = db.scalar(
                select(PaymentWebhookEvent)
                .where(PaymentWebhookEvent.id == event_id)
                .with_for_update(skip_locked=True)
            )
            if (
                event is None or event.processed_at is not None
                or (event.next_attempt_at is not None and event.next_attempt_at > now)
            ):
                db.rollback()
                continue
            if _process_event(db, event.payload):
                event.processed_at = datetime.now(timezone.utc)
                event.next_attempt_at = None
                db.commit()
                result["processed"] += 1
            else:
                db.rollback()
                _schedule_retry(db, event_id)
                result["deferred"] += 1
        except Exception:
            db.rollback()
            logger.exception("Payment webhook replay failed for event_id=%s", event_id)
            try:
                _schedule_retry(db, event_id)
            except Exception:
                db.rollback()
                logger.exception("Could not persist webhook retry schedule for event_id=%s", event_id)
            result["deferred"] += 1
    return result
