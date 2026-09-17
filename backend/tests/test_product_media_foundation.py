"""B1 product-media domain, storage-boundary and configuration tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.models.commerce import Merchant
from app.models.product_media import ProductMediaAsset, ProductMediaAuditEvent, ProductMediaJob
from app.services.product_media import audit_media_event, create_media_job, new_quarantined_asset
from app.services.product_media_storage import (
    FailClosedScanner,
    FakeContentScanner,
    FakeObjectStorage,
    LocalObjectStorage,
    ScanResult,
)
from tests.factories import make_listing, make_store, session


STRONG_SECRET = "x" * 48
PRODUCTION_BASE = {
    "APP_ENV": "production",
    "APP_DEBUG": False,
    "SECRET_KEY": STRONG_SECRET,
    "AUTH_PROVIDER": "msg91_widget",
    "MSG91_AUTH_KEY": "configured-widget-key",
    "DEV_OTP": "",
}


def _source_hash(char: str = "a") -> str:
    return char * 64


def test_listing_owned_asset_has_one_durable_job_and_redacted_audit_data() -> None:
    with session() as db:
        store = make_store(db)
        listing = make_listing(db, store)
        owner = db.get(Merchant, store.merchant_id).owner_user_id
        from app.models.user import User

        user = db.get(User, owner)
        asset = new_quarantined_asset(
            store_product_id=listing.id,
            uploader=user,
            source_object_key="quarantine/listings/opaque-source",
            source_sha256=_source_hash(),
        )
        db.add(asset)
        db.flush()
        first, created = create_media_job(db, asset=asset)
        second, repeated = create_media_job(db, asset=asset)
        audit_media_event(
            db,
            asset=asset,
            actor=user,
            action="media.upload_queued",
            request_id="request-1",
            event_data={"state": "quarantined", "source_object_key": asset.source_object_key},
        )
        db.commit()

        event = db.query(ProductMediaAuditEvent).filter_by(asset_id=asset.id).one()
        assert asset.store_product_id == listing.id
        assert asset.state == "quarantined"
        assert asset.is_primary is False
        assert created is True and repeated is False and first.id == second.id
        assert db.query(ProductMediaJob).filter_by(asset_id=asset.id).count() == 1
        assert event.event_data == {"state": "quarantined"}


def test_database_rejects_public_primary_before_automated_approval() -> None:
    with session() as db:
        store = make_store(db)
        listing = make_listing(db, store)
        from app.models.user import User

        user = db.get(User, db.get(Merchant, store.merchant_id).owner_user_id)
        asset = new_quarantined_asset(
            store_product_id=listing.id,
            uploader=user,
            source_object_key="quarantine/listings/not-approved",
            source_sha256=_source_hash(),
        )
        asset.is_primary = True
        db.add(asset)
        with pytest.raises(IntegrityError, match="primary_approved"):
            db.commit()


def test_only_one_approved_primary_is_allowed_for_a_listing() -> None:
    with session() as db:
        store = make_store(db)
        listing = make_listing(db, store)
        from app.models.user import User

        user = db.get(User, db.get(Merchant, store.merchant_id).owner_user_id)
        for index, key in enumerate(("first", "second")):
            db.add(
                ProductMediaAsset(
                    store_product_id=listing.id,
                    uploader_user_id=user.id,
                    state="approved",
                    source_object_key=f"quarantine/listings/{key}",
                    public_object_key=f"public/listings/{key}.webp",
                    source_sha256=_source_hash(chr(ord("a") + index)),
                    position=index,
                    is_primary=True,
                )
            )
        with pytest.raises(IntegrityError, match="approved_primary"):
            db.commit()


def test_retired_asset_position_can_be_reused_by_a_new_candidate() -> None:
    with session() as db:
        store = make_store(db)
        listing = make_listing(db, store)
        from app.models.user import User

        user = db.get(User, db.get(Merchant, store.merchant_id).owner_user_id)
        db.add_all(
            [
                ProductMediaAsset(
                    store_product_id=listing.id,
                    uploader_user_id=user.id,
                    state="retired",
                    source_object_key="quarantine/listings/retired",
                    source_sha256=_source_hash("r"),
                    position=0,
                ),
                ProductMediaAsset(
                    store_product_id=listing.id,
                    uploader_user_id=user.id,
                    state="quarantined",
                    source_object_key="quarantine/listings/replacement",
                    source_sha256=_source_hash("n"),
                    position=0,
                ),
            ]
        )
        db.commit()


def test_fake_and_local_storage_keep_quarantine_separate_and_reject_path_escape(tmp_path: Path) -> None:
    fake = FakeObjectStorage()
    private = fake.put_quarantine("quarantine/a", b"source", "image/webp")
    public = fake.put_public_derivative("public/a.webp", b"derived", "image/webp")
    assert fake.read_quarantine(private.key) == b"source"
    assert public.key not in fake.quarantine

    local = LocalObjectStorage(tmp_path / "private", tmp_path / "public")
    local.put_quarantine("quarantine/a", b"source", "image/webp")
    assert local.read_quarantine("quarantine/a") == b"source"
    with pytest.raises(ValueError, match="relative opaque"):
        local.put_public_derivative("../escape.webp", b"no", "image/webp")


def test_scanner_adapters_are_explicit_and_default_to_fail_closed() -> None:
    item = FakeObjectStorage().put_quarantine("quarantine/a", b"source", "image/webp")
    scanner = FakeContentScanner(ScanResult(verdict="safe"))
    assert scanner.scan(item).verdict == "safe"
    assert scanner.seen == [item]
    result = FailClosedScanner().scan(item)
    assert result.verdict == "unavailable"
    assert result.reason_code == "scanner_not_configured"


def test_enabled_production_media_rejects_local_storage_and_missing_scanner() -> None:
    with pytest.raises(ValidationError, match="MEDIA_STORAGE_BACKEND"):
        Settings(**PRODUCTION_BASE, PRODUCT_MEDIA_ENABLED=True)

    with pytest.raises(ValidationError, match="mandatory HTTP scanner"):
        Settings(
            **PRODUCTION_BASE,
            PRODUCT_MEDIA_ENABLED=True,
            MEDIA_STORAGE_BACKEND="s3",
            MEDIA_S3_ENDPOINT_URL="https://r2.example.invalid",
            MEDIA_S3_REGION="auto",
            MEDIA_S3_QUARANTINE_BUCKET="private",
            MEDIA_S3_PUBLIC_BUCKET="public",
            MEDIA_PUBLIC_BASE_URL="https://media.example.invalid",
            MEDIA_S3_ACCESS_KEY_ID="id",
            MEDIA_S3_SECRET_ACCESS_KEY="secret",
        )


def test_enabled_production_media_accepts_complete_s3_and_scanner_contract() -> None:
    settings = Settings(
        **PRODUCTION_BASE,
        PRODUCT_MEDIA_ENABLED=True,
        MEDIA_STORAGE_BACKEND="s3",
        MEDIA_S3_ENDPOINT_URL="https://r2.example.invalid",
        MEDIA_S3_REGION="auto",
        MEDIA_S3_QUARANTINE_BUCKET="private",
        MEDIA_S3_PUBLIC_BUCKET="public",
        MEDIA_PUBLIC_BASE_URL="https://media.example.invalid",
        MEDIA_S3_ACCESS_KEY_ID="id",
        MEDIA_S3_SECRET_ACCESS_KEY="secret",
        MEDIA_SCAN_PROVIDER="http",
        MEDIA_SCAN_ENDPOINT_URL="https://scanner.example.invalid",
        MEDIA_SCAN_AUTH_TOKEN="scanner-secret",
    )
    assert settings.PRODUCT_MEDIA_ENABLED is True
    assert settings.MEDIA_STORAGE_BACKEND == "s3"
