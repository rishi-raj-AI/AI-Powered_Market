"""Private product-image upload guard tests."""
from __future__ import annotations

import asyncio
import uuid
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, UploadFile

from app.api.v1.routes import media
from app.models.user import UserRole


def call_upload(db, user, payload=b"\x89PNG\r\n\x1a\nhello", mime="image/png"):
    upload = UploadFile(file=BytesIO(payload), filename="test.png", headers={"content-type": mime})
    return asyncio.run(media.queue_listing_image(uuid.uuid4(), file=upload, db=db, user=user))


def test_upload_fails_closed_when_feature_disabled(monkeypatch):
    monkeypatch.setattr(media.settings, "PRODUCT_MEDIA_ENABLED", False)
    db = MagicMock()
    with pytest.raises(HTTPException) as exc:
        call_upload(db, SimpleNamespace(id=uuid.uuid4(), role=UserRole.MERCHANT))
    assert exc.value.status_code == 503
    db.get.assert_not_called()


def test_upload_fails_closed_without_production_adapter(monkeypatch):
    monkeypatch.setattr(media.settings, "PRODUCT_MEDIA_ENABLED", True)
    monkeypatch.setattr(media.settings, "APP_ENV", "production")
    monkeypatch.setattr(media.settings, "MEDIA_STORAGE_BACKEND", "s3")
    with pytest.raises(HTTPException) as exc:
        call_upload(MagicMock(), SimpleNamespace(id=uuid.uuid4(), role=UserRole.MERCHANT))
    assert exc.value.status_code == 503


def test_upload_denies_other_merchants_before_reading_file(monkeypatch):
    monkeypatch.setattr(media.settings, "PRODUCT_MEDIA_ENABLED", True)
    monkeypatch.setattr(media.settings, "APP_ENV", "test")
    monkeypatch.setattr(media.settings, "MEDIA_STORAGE_BACKEND", "local")
    db = MagicMock()
    db.get.side_effect = [
        SimpleNamespace(store_id=uuid.uuid4()),
        SimpleNamespace(merchant_id=uuid.uuid4()),
        SimpleNamespace(owner_user_id=uuid.uuid4()),
    ]
    with pytest.raises(HTTPException) as exc:
        call_upload(db, SimpleNamespace(id=uuid.uuid4(), role=UserRole.MERCHANT))
    assert exc.value.status_code == 403
