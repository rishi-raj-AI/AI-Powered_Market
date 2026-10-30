"""Publication coordinator tests using private/public fake object storage."""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image
from io import BytesIO

from app.services import product_media_publication
from app.services.product_media_processing import MediaScanUnavailable
from app.services.product_media_storage import FakeObjectStorage, ScanResult


class Scanner:
    def __init__(self, verdict):
        self.verdict = verdict

    def scan_bytes(self, item, source):
        assert source
        return ScanResult(self.verdict)


def setup(monkeypatch):
    monkeypatch.setattr(product_media_publication.settings, "PRODUCT_MEDIA_ENABLED", True)
    storage = FakeObjectStorage()
    buffer = BytesIO()
    Image.new("RGB", (20, 30)).save(buffer, "PNG")
    original = storage.put_quarantine("quarantine/source", buffer.getvalue(), "image/png")
    asset = SimpleNamespace(
        id=uuid.uuid4(), store_product_id=uuid.uuid4(), state="quarantined",
        retired_at=None, public_object_key=None, source_object_key=original.key,
        source_sha256=original.sha256, detected_mime="image/png",
        derivative_sha256=None, width=None, height=None, approved_at=None,
        failure_code=None,
    )
    return storage, asset, MagicMock()


def test_clean_scan_publishes_only_webp_derivative(monkeypatch):
    storage, asset, db = setup(monkeypatch)
    result = product_media_publication.process_quarantined_asset(
        db, asset=asset, storage=storage, scanner=Scanner("clean"), request_id="test"
    )
    assert result.state == "approved"
    assert asset.public_object_key in storage.public
    assert asset.source_object_key in storage.quarantine
    assert storage.public[asset.public_object_key].startswith(b"RIFF")
    assert asset.derivative_sha256
    assert (asset.width, asset.height) == (20, 30)
    db.add.assert_called_once()


def test_rejected_scan_does_not_publish(monkeypatch):
    storage, asset, db = setup(monkeypatch)
    result = product_media_publication.process_quarantined_asset(
        db, asset=asset, storage=storage, scanner=Scanner("infected"), request_id="test"
    )
    assert result.state == "rejected"
    assert storage.public == {}
    assert asset.public_object_key is None
    db.add.assert_called_once()


def test_unavailable_scan_keeps_quarantine(monkeypatch):
    storage, asset, db = setup(monkeypatch)
    with pytest.raises(MediaScanUnavailable):
        product_media_publication.process_quarantined_asset(
            db, asset=asset, storage=storage, scanner=Scanner("unavailable"), request_id="test"
        )
    assert asset.state == "quarantined"
    assert storage.public == {}
    db.add.assert_not_called()


def test_retired_asset_cannot_be_published(monkeypatch):
    storage, asset, db = setup(monkeypatch)
    from datetime import datetime, timezone
    asset.retired_at = datetime.now(timezone.utc)
    result = product_media_publication.process_quarantined_asset(
        db, asset=asset, storage=storage, scanner=Scanner("clean"), request_id="test"
    )
    assert result.reason == "not_eligible"
    assert storage.public == {}
