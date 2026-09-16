"""Template-only banner generation, selection and durable worker jobs.

No external provider, prompt, image asset or untrusted merchant description is
used here.  The worker constructs a deliberately small closed manifest from
authoritative store, locality and currently available catalogue data.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.banners import (
    BannerGenerationJob,
    BannerAuditEvent,
    StoreBannerSelection,
    StoreBannerVersion,
)
from app.models.commerce import Category, Merchant, Product, Store, StoreProduct
from app.models.geography import Village
from app.models.user import User
from app.schemas.banners import BannerManifest, BannerPresentationRead
from app.services.governance_audit import request_id
from app.services.notifications import enqueue_notification

TEMPLATE_ID = "gaonone-store-locality-v1"
TEMPLATE_REVISION = "v1"
GENERATION_QUEUED = "queued"
GENERATION_PROCESSING = "processing"
GENERATION_RETRYING = "retrying"
GENERATION_READY = "ready"
GENERATION_FAILED = "failed"
JOB_SUCCEEDED = "succeeded"
MODERATION_PENDING = "pending"
MODERATION_APPROVED = "approved"
MODERATION_REJECTED = "rejected"
MODERATION_DISABLED = "disabled"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _category_for_store(db: Session, store_id: uuid.UUID) -> str | None:
    """Pick a stable category only from active, currently sellable listings."""
    row = db.execute(
        select(Category.name, func.count(StoreProduct.id).label("count"))
        .join(Product, Product.category_id == Category.id)
        .join(StoreProduct, StoreProduct.product_id == Product.id)
        .where(
            StoreProduct.store_id == store_id,
            StoreProduct.is_available.is_(True),
            StoreProduct.stock_quantity > 0,
            Product.is_active.is_(True),
            Category.is_active.is_(True),
        )
        .group_by(Category.name)
        .order_by(func.count(StoreProduct.id).desc(), Category.name.asc())
        .limit(1)
    ).first()
    return str(row.name) if row else None


def _locality_for_store(db: Session, store: Store) -> str:
    village = db.get(Village, store.village_id)
    # Store creation validates the locality.  This fallback keeps a legacy row
    # from creating an invalid presentation if data is later repaired manually.
    return village.name.strip() if village and village.name.strip() else "Your local area"


def _fingerprint(*, store: Store, locality: str, category: str | None) -> str:
    payload = {
        "template_revision": TEMPLATE_REVISION,
        "store_id": str(store.id),
        "store_name": store.name.strip(),
        "locality": locality,
        "category": category,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def build_manifest(db: Session, store: Store) -> tuple[BannerManifest, str]:
    """Build a first-party presentation manifest; never render merchant text as instructions."""
    locality = _locality_for_store(db, store)
    category = _category_for_store(db, store.id)
    manifest = BannerManifest(
        template_id=TEMPLATE_ID,
        template_revision=TEMPLATE_REVISION,
        title=store.name.strip(),
        locality=locality,
        category=category,
    )
    return manifest, _fingerprint(store=store, locality=locality, category=category)


def public_presentation(selection: StoreBannerSelection | None) -> BannerPresentationRead | None:
    if selection is None or selection.active_version is None:
        return None
    version = selection.active_version
    if (
        version.generation_status != GENERATION_READY
        or version.moderation_status != MODERATION_APPROVED
    ):
        return None
    if not isinstance(version.manifest, dict):
        return None
    try:
        return BannerPresentationRead.model_validate(version.manifest)
    except ValueError:
        # Public reads fail closed if legacy/operator data is not a valid closed manifest.
        return None


def public_presentations_for_stores(
    db: Session, store_ids: list[uuid.UUID]
) -> dict[uuid.UUID, BannerPresentationRead]:
    """Load active public banner manifests for one page in a single query.

    Public store lists are bounded, but they must not add one database round
    trip per store.  The join also deliberately excludes unselected, pending,
    rejected and disabled candidates before a caller can serialize them.
    """
    if not store_ids:
        return {}
    rows = db.execute(
        select(StoreBannerSelection.store_id, StoreBannerVersion)
        .join(
            StoreBannerVersion,
            StoreBannerSelection.active_version_id == StoreBannerVersion.id,
        )
        .where(StoreBannerSelection.store_id.in_(store_ids))
    ).all()
    presentations: dict[uuid.UUID, BannerPresentationRead] = {}
    for store_id, version in rows:
        selection = StoreBannerSelection(store_id=store_id)
        selection.active_version = version
        presentation = public_presentation(selection)
        if presentation is not None:
            presentations[store_id] = presentation
    return presentations


def create_banner_job(
    db: Session,
    *,
    store: Store,
    trigger: str,
    idempotency_key: str,
) -> tuple[BannerGenerationJob, bool]:
    """Create a candidate and job under the caller's store row lock.

    The idempotency key is scoped to a store.  A repeated request returns its
    prior job and cannot manufacture another candidate/version.
    """
    existing = db.scalar(
        select(BannerGenerationJob).where(
            BannerGenerationJob.store_id == store.id,
            BannerGenerationJob.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing, False

    locality = _locality_for_store(db, store)
    category = _category_for_store(db, store.id)
    fingerprint = _fingerprint(store=store, locality=locality, category=category)
    next_version = (
        int(
            db.scalar(
                select(func.coalesce(func.max(StoreBannerVersion.version), 0)).where(
                    StoreBannerVersion.store_id == store.id
                )
            )
            or 0
        )
        + 1
    )
    version = StoreBannerVersion(
        store_id=store.id,
        version=next_version,
        source="template",
        template_revision=TEMPLATE_REVISION,
        input_fingerprint=fingerprint,
        generation_status=GENERATION_QUEUED,
        moderation_status=MODERATION_PENDING,
    )
    db.add(version)
    db.flush()
    job = BannerGenerationJob(
        store_id=store.id,
        version_id=version.id,
        trigger=trigger,
        idempotency_key=idempotency_key,
        status=GENERATION_QUEUED,
    )
    db.add(job)
    db.flush()
    return job, True


def ensure_selection(db: Session, store_id: uuid.UUID) -> StoreBannerSelection:
    selection = db.get(StoreBannerSelection, store_id)
    if selection is None:
        selection = StoreBannerSelection(store_id=store_id)
        db.add(selection)
        db.flush()
    return selection


def audit_banner_action(
    db: Session,
    *,
    store_id: uuid.UUID,
    version_id: uuid.UUID | None,
    actor: User | None,
    action: str,
    request,
    reason_code: str | None = None,
) -> BannerAuditEvent:
    event = BannerAuditEvent(
        store_id=store_id,
        version_id=version_id,
        actor_user_id=actor.id if actor else None,
        action=action,
        reason_code=reason_code,
        request_id=request_id(request),
    )
    db.add(event)
    return event


def _next_backoff(attempt: int) -> timedelta:
    # Template rendering normally succeeds immediately.  The cap prevents a
    # corrupted row or future provider outage from becoming a hot loop.
    return timedelta(seconds=min(300, 5 * (2 ** max(0, attempt - 1))))


def _claim_due_job(db: Session, *, job_id: uuid.UUID | None = None) -> BannerGenerationJob | None:
    now = _now()
    stmt = (
        select(BannerGenerationJob)
        .where(
            or_(
                BannerGenerationJob.status.in_([GENERATION_QUEUED, GENERATION_RETRYING]),
                (
                    (BannerGenerationJob.status == GENERATION_PROCESSING)
                    & (BannerGenerationJob.lease_expires_at.is_not(None))
                    & (BannerGenerationJob.lease_expires_at <= now)
                ),
            ),
            or_(
                BannerGenerationJob.next_attempt_at.is_(None),
                BannerGenerationJob.next_attempt_at <= now,
            ),
        )
        .order_by(BannerGenerationJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job_id is not None:
        stmt = stmt.where(BannerGenerationJob.id == job_id)
    job = db.scalar(stmt)
    if job is None:
        return None
    job.status = GENERATION_PROCESSING
    job.lease_expires_at = now + timedelta(seconds=settings.BANNER_JOB_LEASE_SECONDS)
    return job


def process_due_banner_jobs(
    db: Session, *, limit: int, job_id: uuid.UUID | None = None
) -> dict[str, int]:
    """Drain a bounded number of template jobs without touching external media.

    Each job commits independently so a malformed row cannot delay notification
    or refund work, or the next banner candidate.
    """
    result = {"considered": 0, "succeeded": 0, "retried": 0, "failed": 0}
    requested_job_id = job_id
    for _ in range(1 if requested_job_id is not None else limit):
        job = _claim_due_job(db, job_id=requested_job_id)
        if job is None:
            break
        result["considered"] += 1
        claimed_job_id = job.id
        try:
            version = db.get(StoreBannerVersion, job.version_id)
            store = db.get(Store, job.store_id)
            merchant = (
                db.scalar(select(Merchant).where(Merchant.id == store.merchant_id))
                if store
                else None
            )
            if version is None or store is None or merchant is None:
                raise RuntimeError("banner_references_missing")
            manifest, fingerprint = build_manifest(db, store)
            version.manifest = manifest.model_dump(mode="json")
            version.input_fingerprint = fingerprint
            version.generation_status = GENERATION_READY
            version.failure_code = None
            version.ready_at = _now()
            job.status = JOB_SUCCEEDED
            job.lease_expires_at = None
            job.next_attempt_at = None
            job.failure_code = None
            enqueue_notification(
                db,
                user_id=merchant.owner_user_id,
                event_type="store_banner.ready",
                title="Store banner ready for review",
                body="A new store banner draft is ready for your review.",
                data={"store_id": str(store.id), "banner_version_id": str(version.id)},
            )
            db.commit()
            result["succeeded"] += 1
        except Exception:
            db.rollback()
            # The failure detail might contain data from a future provider or
            # malformed row. Persist a bounded internal code only.
            retry_job = db.scalar(
                select(BannerGenerationJob)
                .where(BannerGenerationJob.id == claimed_job_id)
                .with_for_update()
            )
            if retry_job is None:
                continue
            retry_version = db.get(StoreBannerVersion, retry_job.version_id)
            retry_job.attempt_count += 1
            retry_job.lease_expires_at = None
            retry_job.failure_code = "banner_generation_failed"
            if retry_job.attempt_count >= settings.BANNER_JOB_MAX_ATTEMPTS:
                retry_job.status = GENERATION_FAILED
                retry_job.next_attempt_at = None
                if retry_version is not None:
                    retry_version.generation_status = GENERATION_FAILED
                    retry_version.failure_code = "banner_generation_failed"
                result["failed"] += 1
            else:
                retry_job.status = GENERATION_RETRYING
                retry_job.next_attempt_at = _now() + _next_backoff(retry_job.attempt_count)
                if retry_version is not None:
                    retry_version.generation_status = GENERATION_RETRYING
                    retry_version.failure_code = "banner_generation_failed"
                result["retried"] += 1
            db.commit()
    return result
