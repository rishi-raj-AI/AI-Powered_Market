"""Rider presence updates must serialize with dispatch rider selection."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.api.v1.routes.dispatch import update_rider_presence
from app.models.dispatch import RiderPresence
from app.models.user import User
from app.schemas.dispatch import RiderPresenceUpdate


def test_offline_presence_locks_rider_before_modifying_presence():
    rider_id = uuid4()
    rider = SimpleNamespace(id=rider_id, is_active=True, is_verified=True)
    db = MagicMock()
    db.scalar.return_value = rider
    presence = SimpleNamespace(
        rider_id=rider_id, latitude=18.5, longitude=73.9,
        is_online=True, last_seen_at=None,
    )
    db.get.return_value = presence
    result = update_rider_presence(
        RiderPresenceUpdate(latitude=18.6, longitude=73.8, is_online=False),
        db=db, rider=rider,
    )
    assert result is presence
    assert presence.is_online is False
    assert db.method_calls[0][0] == "scalar"
    assert db.method_calls[1][0] == "get"
    query = db.scalar.call_args.args[0]
    sql = str(query.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql
    assert "users" in sql
    db.get.assert_called_once_with(RiderPresence, rider_id)
    db.commit.assert_called_once()


@pytest.mark.parametrize("active,verified", [(False, True), (True, False)])
def test_presence_rejects_disabled_or_unverified_rider(active, verified):
    rider_id = uuid4()
    rider = SimpleNamespace(id=rider_id)
    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(
        id=rider_id, is_active=active, is_verified=verified,
    )
    with pytest.raises(HTTPException) as exc:
        update_rider_presence(
            RiderPresenceUpdate(latitude=18.6, longitude=73.8, is_online=True),
            db=db, rider=rider,
        )
    assert exc.value.status_code == 403
    db.get.assert_not_called()
    db.commit.assert_not_called()
