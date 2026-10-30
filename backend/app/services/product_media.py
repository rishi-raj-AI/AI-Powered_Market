"""Durable product-media helpers and public approved-derivative selectors."""

from __future__ import annotations

import uuid
from urllib.parse import quote, urlsplit

from app.core.config import settings

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


def approved_listing_media(db: Session, listing_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
    """Public-safe image descriptors; only approved, non-retired derivatives.

    Never return private storage keys; use only configured HTTPS public URLs.
    """
    if not listing_ids or not settings.PRODUCT_MEDIA_ENABLED or not settings.MEDIA_PUBLIC_BASE_URL:
        return {}
    assets = db.scalars(
        select(ProductMediaAsset).where(
            ProductMediaAsset.store_product_id.in_(listing_ids),
            ProductMediaAsset.state == "approved",
            ProductMediaAsset.public_object_key.is_not(None),
            ProductMediaAsset.retired_at.is_(None),
        ).order_by(
            ProductMediaAsset.store_product_id,
            ProductMediaAsset.position,
            ProductMediaAsset.created_at,
        )
    ).all()
    result: dict[uuid.UUID, list[dict]] = {}
    for asset in assets:
        url = public_derivative_url(asset.public_object_key)
        if url is None:
            continue
        result.setdefault(asset.store_product_id, []).append({
            "id": str(asset.id),
            "url": url,
            "alt_text": asset.alt_text,
            "position": asset.position,
            "is_primary": asset.is_primary,
        })
    return result


def public_derivative_url(key: str | None) -> str | None:
    """Resolve only approved derivative object keys against a configured HTTPS origin.

    Never accept absolute URLs, query strings, dot segments, or untrusted
    object paths. The caller must also check database approval and retirement.
    """
    base = settings.MEDIA_PUBLIC_BASE_URL
    if not settings.PRODUCT_MEDIA_ENABLED or not base or not key:
        return None
    parsed = urlsplit(base)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
        return None
    if any(part in {"", ".", ".."} for part in key.split("/")):
        return None
    if key.startswith("/") or "\\" in key or "?" in key or "#" in key or "%" in key or ":" in key:
        return None
    return base.rstrip("/") + "/" + "/".join(quote(part, safe="-_.~") for part in key.split("/"))


def claim_due_media_job(db: Session, *, now=None) -> ProductMediaJob | None:
    """Atomically lease one due job using a row lock; commit before external I/O."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import or_
    now = now or datetime.now(timezone.utc)
    job = db.scalar(
        select(ProductMediaJob)
        .where(
            ProductMediaJob.state.in_(("queued", "processing")),
            ProductMediaJob.attempt_count < settings.MEDIA_JOB_MAX_ATTEMPTS,
            or_(ProductMediaJob.next_attempt_at.is_(None), ProductMediaJob.next_attempt_at <= now),
            or_(ProductMediaJob.lease_expires_at.is_(None), ProductMediaJob.lease_expires_at <= now),
        )
        .order_by(ProductMediaJob.created_at, ProductMediaJob.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is not None:
        job.state = "processing"
        job.attempt_count += 1
        job.lease_expires_at = now + timedelta(seconds=settings.MEDIA_JOB_LEASE_SECONDS)
        job.next_attempt_at = None
    return job
