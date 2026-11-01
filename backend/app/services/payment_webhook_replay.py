"""Replay durable Razorpay webhook events whose provider state was not yet final.

A signed capture callback may arrive while Razorpay still reports "authorized".
The HTTP handler records it without processed_at; this worker retries safely
under row locks. Enable only after sandbox validation of provider rate limits.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.routes.payment_hardening import _process_event
from app.models.integrations import PaymentWebhookEvent

logger = logging.getLogger(__name__)


def replay_pending_payment_webhooks(
    db: Session, *, limit: int = 25, min_age_seconds: int = 60,
) -> dict[str, int]:
    if limit < 1 or min_age_seconds < 0:
        raise ValueError("Invalid webhook replay limits")
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=min_age_seconds)
    ids = db.scalars(
        select(PaymentWebhookEvent.id)
        .where(
            PaymentWebhookEvent.provider == "razorpay",
            PaymentWebhookEvent.processed_at.is_(None),
            PaymentWebhookEvent.created_at <= cutoff,
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
            if event is None or event.processed_at is not None:
                db.rollback()
                continue
            if _process_event(db, event.payload):
                event.processed_at = datetime.now(timezone.utc)
                db.commit()
                result["processed"] += 1
            else:
                db.rollback()
                result["deferred"] += 1
        except Exception:
            db.rollback()
            logger.exception("Payment webhook replay failed for event_id=%s", event_id)
            result["deferred"] += 1
    return result
