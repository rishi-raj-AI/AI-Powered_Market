"""Small durable helpers for the product-media foundation; no public routes yet."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product_media import ProductMediaAsset, ProductMediaAuditEvent, ProductMediaJob
from app.models.user import User

_SAFE_AUDIT_FIELDS = frozenset({"state", "attempt_count", "detected_mime", "byte_size", "width", "height"})


def create_media_job(db: Session, *, asset: ProductMediaAsset) -> tuple[ProductMediaJob, bool]:
    existing = db.scalar(select(ProductMediaJob).where(ProductMediaJob.asset_id == asset.id))
    if existing is not None:
        return existing, False
    job = ProductMediaJob(asset_id=asset.id)
    db.add(job)
    db.flush()
    return job, True


def audit_media_event(
    db: Session,
    *,
    asset: ProductMediaAsset,
    action: str,
    request_id: str,
    actor: User | None = None,
    reason_code: str | None = None,
    event_data: dict | None = None,
) -> ProductMediaAuditEvent:
    """Persist only allowlisted operational data, never binary/object keys."""
    event = ProductMediaAuditEvent(
        asset_id=asset.id,
        store_product_id=asset.store_product_id,
        actor_user_id=actor.id if actor else None,
        action=action[:80],
        reason_code=reason_code[:80] if reason_code else None,
        event_data={key: value for key, value in (event_data or {}).items() if key in _SAFE_AUDIT_FIELDS},
        request_id=request_id[:160],
    )
    db.add(event)
    return event


def new_quarantined_asset(
    *,
    store_product_id: uuid.UUID,
    uploader: User,
    source_object_key: str,
    source_sha256: str,
    position: int = 0,
) -> ProductMediaAsset:
    """Construct a non-public asset. Approval is only a later worker transition."""
    return ProductMediaAsset(
        store_product_id=store_product_id,
        uploader_user_id=uploader.id,
        source_object_key=source_object_key,
        source_sha256=source_sha256,
        position=position,
        state="quarantined",
        is_primary=False,
    )
