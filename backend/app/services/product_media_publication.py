"""Single-asset media publication coordinator.

The caller must acquire an exclusive database job lease before invoking this
function. This boundary never publishes the source and records approval only
after the derivative has been stored and its checksum verified.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.product_media import ProductMediaAsset
from app.services.product_media import audit_media_event
from app.services.product_media_processing import MediaRejected, MediaScanUnavailable, inspect_and_render
from app.services.product_media_storage import ContentScanner, ObjectStorage, StoredMediaObject


@dataclass(frozen=True)
class PublicationResult:
    asset_id: uuid.UUID
    state: str
    reason: str | None = None


def process_quarantined_asset(
    db: Session,
    *,
    asset: ProductMediaAsset,
    storage: ObjectStorage,
    scanner: ContentScanner,
    request_id: str,
) -> PublicationResult:
    """Process only quarantined assets; no implicit retries or commits.

    The worker owns transaction boundaries and job leases. On transient scan
    failures the asset remains quarantined. Permanent rejection is audited.
    """
    if not settings.PRODUCT_MEDIA_ENABLED:
        raise RuntimeError("Product media is disabled")
    if asset.state != "quarantined" or asset.retired_at is not None:
        return PublicationResult(asset.id, asset.state, "not_eligible")
    if asset.public_object_key:
        raise RuntimeError("Quarantined asset unexpectedly has a public key")
    source = storage.read_quarantine(asset.source_object_key)
    original = StoredMediaObject(
        key=asset.source_object_key,
        content_type=asset.detected_mime or "",
        byte_size=len(source),
        sha256=asset.source_sha256,
    )
    try:
        derivative = inspect_and_render(
            source=source, original=original, scanner=scanner,
            max_bytes=settings.MEDIA_UPLOAD_MAX_BYTES,
            max_width=settings.MEDIA_IMAGE_MAX_WIDTH,
            max_height=settings.MEDIA_IMAGE_MAX_HEIGHT,
            max_pixels=settings.MEDIA_IMAGE_MAX_PIXELS,
        )
    except MediaScanUnavailable:
        # Do not change state; retry scheduling is the job worker's concern.
        raise
    except MediaRejected as exc:
        asset.state = "rejected"
        asset.failure_code = str(exc)[:80]
        audit_media_event(
            db, asset=asset, action="media.rejected", request_id=request_id,
            reason_code=asset.failure_code,
        )
        return PublicationResult(asset.id, "rejected", asset.failure_code)

    key = f"public/listings/{asset.store_product_id}/{asset.id}.webp"
    stored = storage.put_public_derivative(key, derivative.content, derivative.content_type)
    expected_hash = hashlib.sha256(derivative.content).hexdigest()
    if stored.sha256 != expected_hash or stored.byte_size != len(derivative.content) or stored.key != key:
        # Do not approve an unverified object. Cleanup failure must not
        # override the original publication error.
        try:
            storage.delete_public_derivative(key)
        except Exception:
            pass
        raise RuntimeError("Public derivative storage verification failed")
    asset.public_object_key = key
    asset.derivative_sha256 = expected_hash
    asset.width = derivative.width
    asset.height = derivative.height
    asset.state = "approved"
    from datetime import datetime, timezone
    asset.approved_at = datetime.now(timezone.utc)
    asset.failure_code = None
    audit_media_event(
        db, asset=asset, action="media.approved", request_id=request_id,
        event_data={"state": "approved", "width": asset.width, "height": asset.height},
    )
    return PublicationResult(asset.id, "approved")
