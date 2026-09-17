from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import ensure_capability, get_db, require_capability, require_roles
from app.core.capabilities import Capability
from app.core.config import settings
from app.models.banners import BannerGenerationJob, StoreBannerSelection, StoreBannerVersion
from app.models.commerce import Merchant, MerchantStatus, Store
from app.models.user import User, UserRole
from app.schemas.banners import (
    BannerAcceptRequest,
    BannerGenerationJobRead,
    BannerModerationRequest,
    BannerRegenerateRequest,
    BannerSelectionRead,
    BannerVersionRead,
)
from app.services.governance_audit import record_admin_action
from app.services.store_banners import (
    GENERATION_READY,
    MODERATION_APPROVED,
    MODERATION_DISABLED,
    MODERATION_REJECTED,
    audit_banner_action,
    create_banner_job,
    ensure_selection,
    public_presentation,
)

merchant_router = APIRouter(prefix="/stores", tags=["Store banners"])
admin_router = APIRouter(prefix="/admin/store-banners", tags=["Store banners"])


def _owned_store(db: Session, store_id: uuid.UUID, user: User, *, lock: bool = False) -> Store:
    stmt = select(Store).where(Store.id == store_id)
    if lock:
        stmt = stmt.with_for_update()
    store = db.scalar(stmt)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    if user.role == UserRole.ADMIN:
        ensure_capability(user, Capability.CATALOG_MANAGE)
        return store
    merchant = db.scalar(select(Merchant).where(Merchant.id == store.merchant_id))
    if merchant is None or merchant.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="You do not own this store")
    if merchant.status != MerchantStatus.APPROVED:
        raise HTTPException(status_code=403, detail="Merchant is not active")
    return store


def _selection_read(db: Session, store_id: uuid.UUID) -> BannerSelectionRead:
    selection = db.get(StoreBannerSelection, store_id)
    if selection is not None and selection.active_version_id is not None:
        selection.active_version = db.get(StoreBannerVersion, selection.active_version_id)
    versions = list(
        db.scalars(
            select(StoreBannerVersion)
            .where(StoreBannerVersion.store_id == store_id)
            .order_by(StoreBannerVersion.version.desc())
        ).all()
    )
    return BannerSelectionRead(
        store_id=store_id,
        revision=selection.revision if selection is not None else 0,
        active_version_id=selection.active_version_id if selection is not None else None,
        active_banner=public_presentation(selection),
        versions=[BannerVersionRead.model_validate(version) for version in versions],
    )


@merchant_router.get("/{store_id}/banner", response_model=BannerSelectionRead)
def get_store_banner(
    store_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
):
    _owned_store(db, store_id, user)
    return _selection_read(db, store_id)


@merchant_router.post(
    "/{store_id}/banner/regenerate",
    response_model=BannerGenerationJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def regenerate_store_banner(
    store_id: uuid.UUID,
    payload: BannerRegenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
):
    store = _owned_store(db, store_id, user, lock=True)
    # A repeated idempotency key must be returned even after the normal quota is
    # reached; otherwise a network retry can be mistaken for a new request.
    existing = db.scalar(
        select(BannerGenerationJob).where(
            BannerGenerationJob.store_id == store.id,
            BannerGenerationJob.idempotency_key == payload.idempotency_key,
        )
    )
    if existing is not None:
        return BannerGenerationJobRead.model_validate(existing)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.BANNER_REGEN_WINDOW_SECONDS)
    used = int(
        db.scalar(
            select(func.count(BannerGenerationJob.id)).where(
                BannerGenerationJob.store_id == store.id,
                BannerGenerationJob.trigger == "merchant_regenerate",
                BannerGenerationJob.created_at >= cutoff,
            )
        )
        or 0
    )
    if used >= settings.BANNER_REGEN_MAX_REQUESTS:
        raise HTTPException(
            status_code=429, detail="Banner regeneration limit reached; try again later"
        )
    job, _ = create_banner_job(
        db,
        store=store,
        trigger="merchant_regenerate",
        idempotency_key=payload.idempotency_key,
    )
    audit_banner_action(
        db,
        store_id=store.id,
        version_id=job.version_id,
        actor=user,
        action="banner.regeneration_requested",
        request=request,
    )
    db.commit()
    db.refresh(job)
    return BannerGenerationJobRead.model_validate(job)


@merchant_router.post(
    "/{store_id}/banner/versions/{version_id}/accept", response_model=BannerSelectionRead
)
def accept_store_banner(
    store_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: BannerAcceptRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
):
    store = _owned_store(db, store_id, user, lock=True)
    version = db.scalar(
        select(StoreBannerVersion)
        .where(StoreBannerVersion.id == version_id, StoreBannerVersion.store_id == store.id)
        .with_for_update()
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Banner version not found")
    if (
        version.generation_status != GENERATION_READY
        or version.moderation_status != MODERATION_APPROVED
    ):
        raise HTTPException(status_code=409, detail="Banner version is not approved for use")
    selection = db.scalar(
        select(StoreBannerSelection)
        .where(StoreBannerSelection.store_id == store.id)
        .with_for_update()
    )
    if selection is None:
        selection = ensure_selection(db, store.id)
    if selection.revision != payload.selection_revision:
        raise HTTPException(
            status_code=409, detail="Banner selection changed; refresh and try again"
        )
    selection.active_version_id = version.id
    selection.selected_by_user_id = user.id
    selection.revision += 1
    audit_banner_action(
        db,
        store_id=store.id,
        version_id=version.id,
        actor=user,
        action="banner.accepted",
        request=request,
    )
    db.commit()
    return _selection_read(db, store.id)


@admin_router.post("/{version_id}/moderation", response_model=BannerVersionRead)
def moderate_store_banner(
    version_id: uuid.UUID,
    payload: BannerModerationRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_capability(Capability.MEDIA_MODERATE)),
):
    version = db.scalar(
        select(StoreBannerVersion).where(StoreBannerVersion.id == version_id).with_for_update()
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Banner version not found")
    target = {
        "approve": MODERATION_APPROVED,
        "reject": MODERATION_REJECTED,
        "disable": MODERATION_DISABLED,
    }[payload.action]
    if payload.action == "approve" and version.generation_status != GENERATION_READY:
        raise HTTPException(status_code=409, detail="Banner version is not ready for approval")
    previous_status = version.moderation_status
    version.moderation_status = target
    version.moderated_by_user_id = admin.id
    version.moderated_at = datetime.now(timezone.utc)
    selection = db.scalar(
        select(StoreBannerSelection)
        .where(StoreBannerSelection.store_id == version.store_id)
        .with_for_update()
    )
    if (
        target in {MODERATION_REJECTED, MODERATION_DISABLED}
        and selection is not None
        and selection.active_version_id == version.id
    ):
        selection.active_version_id = None
        selection.selected_by_user_id = admin.id
        selection.revision += 1
    audit_banner_action(
        db,
        store_id=version.store_id,
        version_id=version.id,
        actor=admin,
        action=f"banner.moderation_{payload.action}",
        request=request,
        reason_code=payload.reason_code,
    )
    record_admin_action(
        db,
        request=request,
        actor=admin,
        action=f"store_banner.{payload.action}",
        capability=Capability.MEDIA_MODERATE,
        resource_type="store_banner_version",
        resource_id=version.id,
        previous_state={"moderation_status": previous_status},
        resulting_state={"moderation_status": target},
        reason=payload.reason_code,
    )
    db.commit()
    db.refresh(version)
    return BannerVersionRead.model_validate(version)
