"""Opt-in, elevated-authority draft publication. No territory activation."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_capability
from app.core.capabilities import Capability
from app.core.config import settings
from app.models.user import User
from app.services.territory_publication import (
    PublicationRejected, publish_initial_draft, publish_revised_draft,
)

router = APIRouter(prefix="/admin/delivery-territories", tags=["Admin Territory Publication"])


class PublishDraftRequest(BaseModel):
    # Required even when null: optimistic concurrency for first publication.
    expected_published_version: int | None = Field(ge=1)
    change_reason: str = Field(min_length=10, max_length=500)


class PublishDraftResponse(BaseModel):
    territory_id: UUID
    published_version: int
    status: str
    coverage_activated: bool = False
    checkout_authoritative: bool = False


@router.post("/{territory_id}/publish-initial-draft", response_model=PublishDraftResponse)
def publish_initial_territory_draft(
    territory_id: UUID,
    payload: PublishDraftRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_capability(Capability.ADMIN_MANAGE)),
) -> PublishDraftResponse:
    """Record a locked, audited version; never activate delivery coverage."""
    if not settings.TERRITORY_ADMIN_PUBLISH_ENABLED:
        raise HTTPException(status_code=404, detail="Territory publication unavailable")
    try:
        result = publish_initial_draft(
            db,
            territory_id=territory_id,
            actor_id=admin.id,
            expected_published_version=payload.expected_published_version,
            reason=payload.change_reason,
        )
        db.commit()
    except PublicationRejected as exc:
        db.rollback()
        status_code = {
            "not_found": 404,
            "invalid_reason": 422,
            "invalid_geometry": 422,
            "version_conflict": 409,
            "not_draft": 409,
        }.get(exc.code, 409)
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    return PublishDraftResponse(
        territory_id=result.territory_id,
        published_version=result.published_version,
        status=result.status,
    )


class RepublishDraftRequest(BaseModel):
    expected_published_version: int = Field(ge=1)
    change_reason: str = Field(min_length=10, max_length=500)


@router.post("/{territory_id}/publish-revised-draft", response_model=PublishDraftResponse)
def publish_revised_territory_draft(
    territory_id: UUID,
    payload: RepublishDraftRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_capability(Capability.ADMIN_MANAGE)),
) -> PublishDraftResponse:
    """Append a changed draft snapshot; never activate delivery coverage."""
    if not settings.TERRITORY_ADMIN_PUBLISH_ENABLED:
        raise HTTPException(status_code=404, detail="Territory publication unavailable")
    try:
        result = publish_revised_draft(
            db,
            territory_id=territory_id,
            actor_id=admin.id,
            expected_published_version=payload.expected_published_version,
            reason=payload.change_reason,
        )
        db.commit()
    except PublicationRejected as exc:
        db.rollback()
        status_code = {
            "not_found": 404,
            "invalid_reason": 422,
            "invalid_geometry": 422,
            "version_conflict": 409,
            "not_draft": 409,
            "unchanged_geometry": 409,
        }.get(exc.code, 409)
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    return PublishDraftResponse(
        territory_id=result.territory_id,
        published_version=result.published_version,
        status=result.status,
    )
