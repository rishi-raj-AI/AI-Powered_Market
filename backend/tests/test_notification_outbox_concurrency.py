"""PostgreSQL row-lock regression for concurrent notification workers."""
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.integrations import NotificationEvent
from app.services.fcm import due_events
from app.services.notifications import enqueue_notification
from tests.factories import make_user, session


def test_locked_outbox_event_is_skipped_by_another_worker():
    with session() as db:
        user = make_user(db)
        event = enqueue_notification(
            db, user_id=user.id, event_type="delivery.task_assigned",
            title="Delivery assigned", body="Pickup is ready.",
        )
        db.commit()
        event_id = event.id

    # Separate real PostgreSQL connections, not an in-memory mock. One
    # worker owns the row; the next must skip it without waiting or sending.
    with SessionLocal() as first, SessionLocal() as second:
        owned = first.scalar(
            select(NotificationEvent)
            .where(NotificationEvent.id == event_id)
            .with_for_update()
        )
        assert owned is not None
        other_worker_ids = {row.id for row in due_events(second, limit=1000, lock=True)}
        assert event_id not in other_worker_ids
        second.rollback()
        first.rollback()

    with SessionLocal() as db:
        # A worker crash/rollback must leave the event eligible for retry.
        assert event_id in {row.id for row in due_events(db, limit=1000)}
