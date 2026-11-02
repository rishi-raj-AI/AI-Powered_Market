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
