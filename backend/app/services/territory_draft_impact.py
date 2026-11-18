"""Read-only point impact analysis of a *published draft* territory.

A candidate draft never grants delivery access. This tool compares an explicit
admin-supplied test point against legacy coverage, using only the latest
immutable draft geometry snapshot with an eligible store assignment. It never
reads customer addresses, changes rows, or participates in checkout.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.delivery_territories import (
    DeliveryTerritory, DeliveryTerritoryVersion, OperatingRegion,
    StoreDeliveryTerritory,
)
from app.services.territory_parity import compare_store_geography
from app.services.territory_preview import (
    _SNAPSHOT_JSON, snapshot_current_territory_geometry,
)


@dataclass(frozen=True)
class DraftImpact:
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


# A separate, explicit draft-only query. Do not broaden the active evaluator:
# doing so could accidentally make unpublished coverage usable by checkout.
_DRAFT_MATCH = text(f"""
    SELECT EXISTS (
        SELECT 1
        FROM delivery_territories t
        JOIN operating_regions r ON r.id = t.operating_region_id
        JOIN store_delivery_territories a ON a.territory_id = t.id
        JOIN delivery_territory_versions v
          ON v.territory_id = t.id AND v.version = t.published_version
        WHERE t.id = :territory_id AND a.store_id = :store_id
          AND t.status = 'draft' AND r.status = 'active'
          AND a.status = 'active' AND a.delivery_enabled = true
          AND v.published_at IS NOT NULL
          AND v.snapshot = {_SNAPSHOT_JSON}
          AND (a.effective_from IS NULL OR a.effective_from <= :at)
          AND (a.effective_until IS NULL OR a.effective_until > :at)
          AND (t.effective_from IS NULL OR t.effective_from <= :at)
          AND (t.effective_until IS NULL OR t.effective_until > :at)
          AND (
            (t.geometry_type = 'circle' AND t.center_latitude IS NOT NULL
             AND t.center_longitude IS NOT NULL AND t.radius_km > 0
             AND ST_DWithin(
                ST_SetSRID(ST_MakePoint(
                  t.center_longitude::double precision,
                  t.center_latitude::double precision
                ),4326)::geography,
                ST_SetSRID(ST_MakePoint(:longitude,:latitude),4326)::geography,
                t.radius_km::double precision * 1000.0
             ))
            OR (t.geometry_type = 'polygon' AND t.geometry IS NOT NULL
                AND ST_Covers(
                  t.geometry, ST_SetSRID(ST_MakePoint(:longitude,:latitude),4326)
                ))
          )
          AND NOT EXISTS (
            SELECT 1 FROM delivery_territory_exclusions e
            WHERE e.territory_id = t.id
              AND ST_Covers(
                e.geometry, ST_SetSRID(ST_MakePoint(:longitude,:latitude),4326)
              )
          )
    )
""")


def compare_published_draft_geography(
    db: Session, *, store_id: UUID, territory_id: UUID,
    latitude: float, longitude: float, evaluated_at: datetime | None = None,
) -> DraftImpact | None:
    """Return point-level candidate impact, never an activation decision.

    A missing assignment, incomplete version, changed geometry or inactive
    operating region is NOT a negative match: it is NOT_COMPARABLE. This avoids
    reporting false contractions from an ineligible draft.
    """
    if not (
        isfinite(latitude) and isfinite(longitude)
        and -90 <= latitude <= 90 and -180 <= longitude <= 180
    ):
        raise ValueError("Location coordinates are invalid")
    at = evaluated_at or datetime.now(timezone.utc)
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Evaluation time must be timezone-aware")

    legacy = compare_store_geography(db, store_id, latitude, longitude)
    territory = db.get(DeliveryTerritory, territory_id)
    if legacy is None or territory is None:
        return None

    issue = None
    if territory.status != "draft":
        issue = "TERRITORY_NOT_DRAFT"
    else:
        region = db.get(OperatingRegion, territory.operating_region_id)
        if region is None or region.status != "active":
            issue = "REGION_NOT_ACTIVE"
        elif (
            (territory.effective_from is not None and territory.effective_from > at)
            or (territory.effective_until is not None and territory.effective_until <= at)
        ):
            issue = "TERRITORY_OUTSIDE_EFFECTIVE_WINDOW"

    assignment = db.scalar(select(StoreDeliveryTerritory).where(
        StoreDeliveryTerritory.territory_id == territory_id,
        StoreDeliveryTerritory.store_id == store_id,
    ))
    if issue is None and assignment is None:
        issue = "STORE_NOT_ASSIGNED"
    if issue is None and assignment is not None and (
        assignment.status != "active" or not assignment.delivery_enabled
        or (assignment.effective_from is not None and assignment.effective_from > at)
        or (assignment.effective_until is not None and assignment.effective_until <= at)
    ):
        issue = "ASSIGNMENT_NOT_ELIGIBLE"

    version_number = territory.published_version
    if issue is None:
        version = db.scalar(select(DeliveryTerritoryVersion).where(
            DeliveryTerritoryVersion.territory_id == territory_id,
            DeliveryTerritoryVersion.version == version_number,
        )) if version_number is not None else None
        highest = db.scalar(select(func.max(DeliveryTerritoryVersion.version)).where(
            DeliveryTerritoryVersion.territory_id == territory_id,
        ))
        if (
            version is None or version.published_at is None
            or highest != version_number or not isinstance(version.snapshot, dict)
            or version.snapshot.get("snapshot_format") != "delivery-geometry-v1"
        ):
            issue = "INVALID_PUBLICATION_HISTORY"
        elif snapshot_current_territory_geometry(db, territory_id) != version.snapshot:
            issue = "UNPUBLISHED_GEOMETRY_CHANGES"

    draft_match = None
    if issue is None:
        draft_match = bool(db.execute(_DRAFT_MATCH, {
            "store_id": store_id, "territory_id": territory_id,
            "latitude": latitude, "longitude": longitude, "at": at,
        }).scalar_one())

    if issue or legacy.legacy_geographic_match is None:
        status = "NOT_COMPARABLE"
    elif legacy.legacy_geographic_match and draft_match:
        status = "MATCH_BOTH"
    elif legacy.legacy_geographic_match:
        status = "LEGACY_ONLY"
    elif draft_match:
        status = "DRAFT_ONLY"
    else:
        status = "NEITHER"

    return DraftImpact(
        store_id=store_id, territory_id=territory_id,
        published_version=version_number,
        legacy_geographic_match=legacy.legacy_geographic_match,
        draft_geographic_match=draft_match,
        parity_status=status,
        legacy_configuration_issue=legacy.legacy_configuration_issue,
        draft_issue=issue,
    )
