"""The notification outbox reliability contract.

These assertions previously matched exact source text (including whitespace),
so they broke on reformatting while proving nothing about behaviour. They now
assert the guarantees themselves:

1. Enqueuing joins the caller's transaction and never sends anything, so a
   business transaction that rolls back cannot leave a stray notification —
   and committing one is never mistaken for having delivered a push.
2. Draining only ever picks up events that are actually pending and due.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.integrations import NotificationEvent
from app.services import fcm, notifications
from app.services.fcm import STATUS_PENDING, STATUS_SENT, due_events
from app.services.notifications import enqueue_notification
from tests.factories import make_user, session


def test_enqueue_joins_the_callers_transaction_and_does_not_commit() -> None:
    with session() as db:
        user = make_user(db)
        db.commit()
        event = enqueue_notification(
            db,
            user_id=user.id,
            event_type="order.placed",
            title="Order placed",
            body="Your order has been placed.",
        )
        event_id = event.id
        # Rolling back the business transaction must take the notification with it.
        db.rollback()

    with session() as db:
        assert db.get(NotificationEvent, event_id) is None


def test_enqueue_never_delivers() -> None:
    """A stored event is a record that something happened, not a delivered push."""
    source = inspect.getsource(notifications.enqueue_notification)
    assert "deliver_event" not in source
    assert "commit" not in source

    with session() as db:
        user = make_user(db)
        event = enqueue_notification(
            db,
            user_id=user.id,
            event_type="order.placed",
            title="Order placed",
            body="Your order has been placed.",
        )
        db.commit()
        assert event.status == STATUS_PENDING
        assert event.sent_at is None


def test_draining_only_picks_up_pending_due_events(monkeypatch) -> None:
    monkeypatch.setattr(fcm, "_firebase", lambda: None)
    monkeypatch.setattr(fcm.settings, "FCM_PROJECT_ID", None)

    with session() as db:
        user = make_user(db)
        db.commit()

        def _make(status: str, next_attempt_at=None) -> NotificationEvent:
            event = enqueue_notification(
                db,
                user_id=user.id,
                event_type="order.placed",
                title="Order placed",
                body="Body",
            )
            event.status = status
            event.next_attempt_at = next_attempt_at
            db.flush()
            return event

        pending_now = _make(STATUS_PENDING)
        already_sent = _make(STATUS_SENT)
        backing_off = _make(
            STATUS_PENDING, datetime.now(timezone.utc) + timedelta(minutes=30)
        )
        db.commit()

        due_ids = {event.id for event in due_events(db, limit=500)}
        assert pending_now.id in due_ids
        assert already_sent.id not in due_ids
        assert backing_off.id not in due_ids


def test_stored_events_are_readable_regardless_of_push_delivery() -> None:
    """In-app history must not depend on a push provider being reachable."""
    with session() as db:
        user = make_user(db)
        enqueue_notification(
            db,
            user_id=user.id,
            event_type="delivery.otp",
            title="Delivery verification code",
            body="Your code is 123456.",
        )
        db.commit()

        stored = db.scalars(
            select(NotificationEvent).where(NotificationEvent.user_id == user.id)
        ).all()
        assert len(stored) == 1
        assert stored[0].status == STATUS_PENDING
