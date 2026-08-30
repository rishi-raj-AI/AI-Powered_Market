from pathlib import Path


def test_notification_enqueue_does_not_commit_or_deliver() -> None:
    source = Path("app/services/notifications.py").read_text()
    assert "db.add(event)" in source
    assert "db.commit(" not in source
    assert "deliver_event(" not in source


def test_notification_flush_only_processes_pending_events() -> None:
    source = Path("app/services/fcm.py").read_text()
    assert 'NotificationEvent.status=="pending"' in source
    assert "deliver_event(db,event)" in source
