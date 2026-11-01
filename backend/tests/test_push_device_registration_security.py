"""Protect FCM registrations against cross-account token takeover."""
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from app.api.v1.routes.notifications import register_device
from app.schemas.integrations import DeviceRegistrationCreate


def _payload():
    return DeviceRegistrationCreate(token="device-token-" + "x" * 30, platform="android")


def _user():
    user = MagicMock()
    user.id = uuid4()
    return user


def test_active_device_token_cannot_be_rebound_to_another_user():
    db = MagicMock()
    existing = MagicMock()
    existing.user_id = uuid4()
    existing.is_active = True
    db.scalar.return_value = existing
    with pytest.raises(HTTPException) as exc:
        register_device(_payload(), db=db, user=_user())
    assert exc.value.status_code == 409
    db.commit.assert_not_called()
    assert existing.is_active is True
    statement = db.scalar.call_args.args[0]
    assert "FOR UPDATE" in str(statement.compile(dialect=postgresql.dialect()))


def test_same_user_can_refresh_existing_registration():
    db = MagicMock()
    user = _user()
    existing = MagicMock()
    existing.user_id = user.id
    existing.is_active = True
    db.scalar.return_value = existing
    assert register_device(_payload(), db=db, user=user) is existing
    db.commit.assert_called_once()
    assert existing.user_id == user.id


def test_inactive_token_can_be_reclaimed_after_logout():
    db = MagicMock()
    existing = MagicMock()
    existing.user_id = uuid4()
    existing.is_active = False
    db.scalar.return_value = existing
    user = _user()
    assert register_device(_payload(), db=db, user=user) is existing
    assert existing.user_id == user.id
    assert existing.is_active is True
    db.commit.assert_called_once()


def test_first_registration_unique_token_race_returns_conflict():
    db = MagicMock()
    db.scalar.return_value = None
    db.commit.side_effect = IntegrityError("insert", {}, Exception("unique violation"))
    with pytest.raises(HTTPException) as exc:
        register_device(_payload(), db=db, user=_user())
    assert exc.value.status_code == 409
    db.rollback.assert_called_once()


def test_push_config_requires_project_and_worker_credentials(monkeypatch):
    from app.api.v1.routes.notifications import notification_config
    from app.core.config import settings

    monkeypatch.setattr(settings, "FCM_PROJECT_ID", "gaonone-test")
    monkeypatch.setattr(settings, "FCM_SERVICE_ACCOUNT_JSON_B64", "")
    assert notification_config().enabled is False
    monkeypatch.setattr(settings, "FCM_SERVICE_ACCOUNT_JSON_B64", "configured-credential")
    assert notification_config().enabled is True
    monkeypatch.setattr(settings, "FCM_PROJECT_ID", "")
    assert notification_config().enabled is False
