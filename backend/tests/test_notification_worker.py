"""P1: the notification outbox has to drain itself.

app/scripts/dispatch_notifications.py existed but had zero callers anywhere —
not in the Makefile, the systemd unit, the compose file or CI — so events piled
up as 'pending' and only moved when an admin pressed a button.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.integrations import NotificationEvent
from app.services import fcm
from app.services.fcm import (
    MAX_DELIVERY_ATTEMPTS,
    STATUS_DEAD,
    STATUS_IN_APP_ONLY,
    STATUS_PENDING,
    STATUS_SENT,
    deliver_event,
    due_events,
    flush_pending,
)
from app.services.notifications import enqueue_notification
from tests.factories import make_user, session


class _Messaging:
    """Stands in for firebase_admin.messaging."""

    def __init__(self, error: Exception | None = None):
        self.sent = 0
        self._error = error

    def Message(self, **kwargs):  # noqa: N802 - mirrors the provider API
        return kwargs

    def Notification(self, **kwargs):  # noqa: N802 - mirrors the provider API
        return kwargs

    def send(self, message):
        if self._error is not None:
            raise self._error
        self.sent += 1


def _event(db, user, *, status=STATUS_PENDING) -> NotificationEvent:
    event = enqueue_notification(
        db,
        user_id=user.id,
        event_type="order.placed",
        title="Order placed",
        body="Your order has been placed.",
        data={"order_id": "abc"},
    )
    event.status = status
    db.flush()
    return event


def _register_device(db, user) -> None:
    from app.models.integrations import DeviceRegistration

    db.add(
        DeviceRegistration(
            user_id=user.id,
            token=f"token-{user.id}",
            platform="android",
            is_active=True,
        )
    )
    db.flush()


def test_enqueue_does_not_send_and_stays_transactional() -> None:
    """Persisting an event is not the same as delivering a push."""
    with session() as db:
        user = make_user(db)
        event = _event(db, user)
        assert event.status == STATUS_PENDING
        assert event.sent_at is None
        assert event.attempt_count == 0
        db.rollback()


def test_worker_delivers_pending_events(monkeypatch) -> None:
    messaging = _Messaging()
    monkeypatch.setattr(fcm, "_firebase", lambda: messaging)
    with session() as db:
        user = make_user(db)
        _register_device(db, user)
        event = _event(db, user)
        db.commit()

        deliver_event(db, event)
        db.commit()

        assert event.status == STATUS_SENT
        assert event.sent_at is not None
        assert messaging.sent == 1


def test_failed_delivery_backs_off_instead_of_blocking_the_queue(monkeypatch) -> None:
    messaging = _Messaging(error=RuntimeError("provider unavailable"))
    monkeypatch.setattr(fcm, "_firebase", lambda: messaging)
    with session() as db:
        user = make_user(db)
        _register_device(db, user)
        event = _event(db, user)
        db.commit()

        deliver_event(db, event)
        db.commit()

        assert event.status == STATUS_PENDING
        assert event.attempt_count == 1
        assert event.last_error
        # Scheduled for later, so it is not retried in a hot loop and does not
        # sit at the head of the queue blocking newer events.
        assert event.next_attempt_at > datetime.now(timezone.utc)
        assert event.id not in {due.id for due in due_events(db)}


def test_permanently_failing_event_is_retired(monkeypatch) -> None:
    messaging = _Messaging(error=RuntimeError("provider unavailable"))
    monkeypatch.setattr(fcm, "_firebase", lambda: messaging)
    with session() as db:
        user = make_user(db)
        _register_device(db, user)
        event = _event(db, user)
        db.commit()

        for _ in range(MAX_DELIVERY_ATTEMPTS):
            event.next_attempt_at = None
            deliver_event(db, event)
            db.commit()

        assert event.status == STATUS_DEAD
        assert event.attempt_count == MAX_DELIVERY_ATTEMPTS
        # A retired event never comes back to block the queue.
        assert event.id not in {due.id for due in due_events(db)}


def test_a_poison_event_does_not_stall_newer_ones(monkeypatch) -> None:
    """The original failure mode: one bad event at the head of the queue."""
    calls = {"n": 0}

    class _FlakyMessaging(_Messaging):
        def send(self, message):
            calls["n"] += 1
            if message["token"].endswith("poison"):
                raise RuntimeError("permanent failure")
            self.sent += 1

    monkeypatch.setattr(fcm, "_firebase", lambda: _FlakyMessaging())
    from app.models.integrations import DeviceRegistration

    with session() as db:
        poisoned = make_user(db)
        healthy = make_user(db)
        db.add(DeviceRegistration(user_id=poisoned.id, token="dev-poison", platform="android"))
        db.add(DeviceRegistration(user_id=healthy.id, token="dev-ok", platform="android"))
        db.flush()
        bad = _event(db, poisoned)
        bad.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        good = _event(db, healthy)
        db.commit()
        bad_id, good_id = bad.id, good.id

        flush_pending(db)

        db.refresh(bad)
        db.refresh(good)
        # The healthy event went out on the same pass as the failing one.
        assert good.status == STATUS_SENT
        assert bad.status == STATUS_PENDING
        assert bad.attempt_count == 1
        assert bad_id != good_id


def test_unconfigured_push_marks_events_in_app_only(monkeypatch) -> None:
    monkeypatch.setattr(fcm, "_firebase", lambda: None)
    monkeypatch.setattr(fcm.settings, "FCM_PROJECT_ID", None)
    with session() as db:
        user = make_user(db)
        event = _event(db, user)
        db.commit()

        deliver_event(db, event)
        db.commit()

        # Honest: no push was delivered, and the in-app record is the delivery.
        assert event.status == STATUS_IN_APP_ONLY
        assert event.sent_at is None


def test_configured_but_broken_push_is_retried_not_silently_dropped(monkeypatch) -> None:
    monkeypatch.setattr(fcm, "_firebase", lambda: None)
    monkeypatch.setattr(fcm.settings, "FCM_PROJECT_ID", "gaonone-test")
    with session() as db:
        user = make_user(db)
        event = _event(db, user)
        db.commit()

        deliver_event(db, event)
        db.commit()

        assert event.status == STATUS_PENDING
        assert event.attempt_count == 1
        assert "could not be initialised" in event.last_error


def test_worker_tick_is_safe_when_there_is_nothing_to_do() -> None:
    from app.scripts.worker import tick

    outcome = tick()
    assert "notifications" in outcome
    assert "refunds" in outcome
    assert "error" not in outcome["notifications"]
    assert "error" not in outcome["refunds"]
