import uuid

from sqlalchemy import select

from app.models.integrations import NotificationEvent
from app.services.notifications import enqueue_notification


def test_notification_event_is_transactional_outbox(db_session) -> None:
    user_id = uuid.uuid4()
    event = enqueue_notification(
        db_session,
        user_id=user_id,
        event_type="order.lifecycle",
        title="Order update",
        body="Your order changed state.",
        data={"order_id": "order-1"},
    )
    assert event.status == "pending"
    db_session.flush()
    assert db_session.scalar(select(NotificationEvent).where(NotificationEvent.id == event.id)) is event
    db_session.rollback()
    assert db_session.scalar(select(NotificationEvent).where(NotificationEvent.id == event.id)) is None
