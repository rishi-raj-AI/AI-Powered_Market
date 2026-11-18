"""Admin-only, opt-in, read-only geographic territory preview.

This endpoint does not make checkout decisions, create orders, publish
territories, or expose customer addresses. Coordinates are accepted in a POST
body to keep them out of ordinary URL/access logs.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_capability
from app.core.capabilities import Capability
from app.core.config import settings
from app.models.commerce import Store
from app.models.user import User
from app.services.territory_preview import match_active_store_territory
from app.services.territory_activation_preflight import inspect_territory_activation_preflight
from app.services.territory_parity import compare_store_geography
from app.services.territory_draft_impact import compare_published_draft_geography

router = APIRouter(prefix="/admin/delivery-territories", tags=["Admin Territory Preview"])


class TerritoryPreviewRequest(BaseModel):
    store_id: UUID
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


class TerritoryPreviewResponse(BaseModel):
    geographic_match: bool
    territory_id: UUID | None = None
    assignment_id: UUID | None = None
    geometry_type: str | None = None
    checkout_authoritative: bool = False


@router.post("/preview", response_model=TerritoryPreviewResponse)
def preview_store_territory(
    payload: TerritoryPreviewRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_capability(Capability.GEOGRAPHY_MANAGE)),
) -> TerritoryPreviewResponse:
    """Preview an active published geographic match; no writes or fee claims."""
    if not settings.TERRITORY_ADMIN_PREVIEW_ENABLED:
        raise HTTPException(status_code=404, detail="Territory preview unavailable")
    if db.get(Store, payload.store_id) is None:
        raise HTTPException(status_code=404, detail="Store not found")
    match = match_active_store_territory(
        db, payload.store_id, payload.latitude, payload.longitude,
    )
    if match is None:
        return TerritoryPreviewResponse(geographic_match=False)
    return TerritoryPreviewResponse(
        geographic_match=True,
        territory_id=match.territory_id,
        assignment_id=match.assignment_id,
        geometry_type=match.geometry_type,
    )


class TerritoryActivationPreflightResponse(BaseModel):
    territory_id: UUID
    published_version: int | None
    total_assignments: int
    eligible_assignments: int
    issues: list[str]
    technical_checks_passed: bool
    activation_authorized: bool = False
    checkout_authoritative: bool = False


@router.get("/{territory_id}/activation-preflight", response_model=TerritoryActivationPreflightResponse)
def territory_activation_preflight(
    territory_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_capability(Capability.GEOGRAPHY_MANAGE)),
) -> TerritoryActivationPreflightResponse:
    """Read-only technical gate, never approval to activate or use for checkout."""
    if not settings.TERRITORY_ADMIN_PREVIEW_ENABLED:
        raise HTTPException(status_code=404, detail="Territory preview unavailable")
    result = inspect_territory_activation_preflight(db, territory_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Territory not found")
    return TerritoryActivationPreflightResponse(
        territory_id=result.territory_id,
        published_version=result.published_version,
        total_assignments=result.total_assignments,
        eligible_assignments=result.eligible_assignments,
        issues=list(result.issues),
        technical_checks_passed=result.technical_checks_passed,
    )


class TerritoryParityRequest(BaseModel):
    store_id: UUID
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


class TerritoryParityResponse(BaseModel):
    store_id: UUID
    legacy_geographic_match: bool | None
    territory_geographic_match: bool
    parity_status: str
    legacy_configuration_issue: str | None = None
    territory_id: UUID | None = None
    checkout_authoritative: bool = False
    activation_authorized: bool = False


@router.post("/parity-preview", response_model=TerritoryParityResponse)
def preview_territory_parity(
    payload: TerritoryParityRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_capability(Capability.GEOGRAPHY_MANAGE)),
) -> TerritoryParityResponse:
    """Compare geographic coverage only; never check out or activate a territory."""
    if not settings.TERRITORY_ADMIN_PREVIEW_ENABLED:
        raise HTTPException(status_code=404, detail="Territory preview unavailable")
    report = compare_store_geography(
        db, payload.store_id, payload.latitude, payload.longitude,
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return TerritoryParityResponse(
        store_id=report.store_id,
        legacy_geographic_match=report.legacy_geographic_match,
        territory_geographic_match=report.territory_geographic_match,
        parity_status=report.parity_status,
        legacy_configuration_issue=report.legacy_configuration_issue,
        territory_id=report.territory_id,
    )


class DraftImpactRequest(BaseModel):
    store_id: UUID
    territory_id: UUID
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


class DraftImpactResponse(BaseModel):
    store_id: UUID
    territory_id: UUID
    published_version: int | None
    legacy_geographic_match: bool | None
    draft_geographic_match: bool | None
    parity_status: str
    legacy_configuration_issue: str | None = None
    draft_issue: str | None = None
    checkout_authoritative: bool = False
    activation_authorized: bool = False


@router.post("/draft-impact-preview", response_model=DraftImpactResponse)
def preview_published_draft_impact(
    payload: DraftImpactRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_capability(Capability.GEOGRAPHY_MANAGE)),
) -> DraftImpactResponse:
    """Compare an immutable draft snapshot; never authorize checkout or activation."""
    if not settings.TERRITORY_ADMIN_PREVIEW_ENABLED:
        raise HTTPException(status_code=404, detail="Territory preview unavailable")
    result = compare_published_draft_geography(
        db, store_id=payload.store_id, territory_id=payload.territory_id,
        latitude=payload.latitude, longitude=payload.longitude,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Store or territory not found")
    return DraftImpactResponse(
        store_id=result.store_id,
        territory_id=result.territory_id,
        published_version=result.published_version,
        legacy_geographic_match=result.legacy_geographic_match,
        draft_geographic_match=result.draft_geographic_match,
        parity_status=result.parity_status,
        legacy_configuration_issue=result.legacy_configuration_issue,
        draft_issue=result.draft_issue,
    )
