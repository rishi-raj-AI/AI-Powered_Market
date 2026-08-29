from uuid import uuid4

from sqlalchemy import select

from app.core.request_context import request_id_var
from app.db.session import SessionLocal
from app.models.integrations import NotificationEvent
from app.models.user import User
from app.services.fcm import _claim_pending
from app.services.notifications import enqueue_notification


def test_notification_outbox_is_idempotent_correlated_and_claimed_once() -> None:
    key = f"test-outbox-{uuid4()}"
    correlation = f"req-{uuid4()}"
    token = request_id_var.set(correlation)
    event_id = None
    try:
        with SessionLocal() as db:
            user = db.scalar(select(User).order_by(User.created_at).limit(1))
            assert user is not None
            first = enqueue_notification(
                db,
                user_id=user.id,
                event_type="test.outbox",
                title="Test",
                body="Reliable event",
                idempotency_key=key,
            )
            duplicate = enqueue_notification(
                db,
                user_id=user.id,
                event_type="test.outbox",
                title="Test",
                body="Reliable event",
                idempotency_key=key,
            )
            db.commit()
            assert first.id == duplicate.id
            assert first.request_id == correlation
            event_id = first.id

        with SessionLocal() as db:
            claimed = _claim_pending(db, 100)
            matching = [event for event in claimed if event.id == event_id]
            assert len(matching) == 1
            assert matching[0].status == "processing"
            assert matching[0].attempts == 1
            assert matching[0].locked_at is not None

        with SessionLocal() as db:
            second_claim = _claim_pending(db, 100)
            assert all(event.id != event_id for event in second_claim)
    finally:
        request_id_var.reset(token)
        if event_id is not None:
            with SessionLocal() as db:
                event = db.get(NotificationEvent, event_id)
                if event is not None:
                    db.delete(event)
                    db.commit()
