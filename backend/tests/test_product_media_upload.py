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


def test_owner_upload_queues_private_asset_without_exposing_storage_key(monkeypatch):
    from app.services.product_media_storage import FakeObjectStorage
    monkeypatch.setattr(media.settings, "PRODUCT_MEDIA_ENABLED", True)
    monkeypatch.setattr(media.settings, "APP_ENV", "test")
    monkeypatch.setattr(media.settings, "MEDIA_STORAGE_BACKEND", "local")
    owner_id = uuid.uuid4()
    db = MagicMock()
    db.get.side_effect = [
        SimpleNamespace(store_id=uuid.uuid4()),
        SimpleNamespace(merchant_id=uuid.uuid4()),
        SimpleNamespace(owner_user_id=owner_id),
    ]
    db.query.return_value.filter.return_value.count.return_value = 0
    storage = FakeObjectStorage()
    monkeypatch.setattr(media, "LocalObjectStorage", lambda *args: storage)
    monkeypatch.setattr(media.rate_limiter, "enforce", lambda *args, **kwargs: None)
    result = call_upload(db, SimpleNamespace(id=owner_id, role=UserRole.MERCHANT))
    assert result["state"] == "quarantined"
    assert "source_object_key" not in result and "url" not in result
    assert len(storage.quarantine) == 1 and not storage.public
    db.commit.assert_called_once()


def test_owner_upload_rejects_invalid_magic_before_storage(monkeypatch):
    monkeypatch.setattr(media.settings, "PRODUCT_MEDIA_ENABLED", True)
    monkeypatch.setattr(media.settings, "APP_ENV", "test")
    monkeypatch.setattr(media.settings, "MEDIA_STORAGE_BACKEND", "local")
    owner = uuid.uuid4()
    db = MagicMock()
    db.get.side_effect = [
        SimpleNamespace(store_id=uuid.uuid4()),
        SimpleNamespace(merchant_id=uuid.uuid4()),
        SimpleNamespace(owner_user_id=owner),
    ]
    monkeypatch.setattr(media.rate_limiter, "enforce", lambda *args, **kwargs: None)
    with pytest.raises(HTTPException) as exc:
        call_upload(db, SimpleNamespace(id=owner, role=UserRole.MERCHANT), payload=b"not png")
    assert exc.value.status_code == 415
    db.commit.assert_not_called()


def test_owner_upload_enforces_listing_image_limit(monkeypatch):
    monkeypatch.setattr(media.settings, "PRODUCT_MEDIA_ENABLED", True)
    monkeypatch.setattr(media.settings, "APP_ENV", "test")
    monkeypatch.setattr(media.settings, "MEDIA_STORAGE_BACKEND", "local")
    owner = uuid.uuid4()
    db = MagicMock()
    db.get.side_effect = [
        SimpleNamespace(store_id=uuid.uuid4()),
        SimpleNamespace(merchant_id=uuid.uuid4()),
        SimpleNamespace(owner_user_id=owner),
    ]
    db.query.return_value.filter.return_value.count.return_value = media.settings.MEDIA_IMAGE_MAX_PER_LISTING
    monkeypatch.setattr(media.rate_limiter, "enforce", lambda *args, **kwargs: None)
    with pytest.raises(HTTPException) as exc:
        call_upload(db, SimpleNamespace(id=owner, role=UserRole.MERCHANT))
    assert exc.value.status_code == 409
    db.commit.assert_not_called()


def test_failed_database_write_removes_quarantine_object(monkeypatch):
    from app.services.product_media_storage import FakeObjectStorage
    monkeypatch.setattr(media.settings, "PRODUCT_MEDIA_ENABLED", True)
    monkeypatch.setattr(media.settings, "APP_ENV", "test")
    monkeypatch.setattr(media.settings, "MEDIA_STORAGE_BACKEND", "local")
    owner = uuid.uuid4()
    db = MagicMock()
    db.get.side_effect = [
        SimpleNamespace(store_id=uuid.uuid4()),
        SimpleNamespace(merchant_id=uuid.uuid4()),
        SimpleNamespace(owner_user_id=owner),
    ]
    db.query.return_value.filter.return_value.count.return_value = 0
    db.flush.side_effect = RuntimeError("database failure")
    storage = FakeObjectStorage()
    monkeypatch.setattr(media, "LocalObjectStorage", lambda *args: storage)
    monkeypatch.setattr(media.rate_limiter, "enforce", lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match="database failure"):
        call_upload(db, SimpleNamespace(id=owner, role=UserRole.MERCHANT))
    assert storage.quarantine == {}
    db.rollback.assert_called_once()
