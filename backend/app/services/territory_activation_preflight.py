"""Read-only technical preflight for draft territory activation review.

This is not an activation approval, parity check, or checkout eligibility.
It intentionally does not mutate rows or disclose customer coordinates.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.commerce import Merchant, MerchantStatus, Store
from app.models.delivery_territories import (
    DeliveryTerritory, DeliveryTerritoryVersion, OperatingRegion,
    StoreDeliveryTerritory,
)
from app.services.territory_preview import snapshot_current_territory_geometry


@dataclass(frozen=True)
class TerritoryActivationPreflight:
    territory_id: UUID
    published_version: int | None
    total_assignments: int
    eligible_assignments: int
    issues: tuple[str, ...]
    technical_checks_passed: bool
    activation_authorized: bool = False
    checkout_authoritative: bool = False


_GEOMETRY_VALID = text("""
    SELECT CASE
      WHEN geometry_type = 'circle' THEN
        center_latitude IS NOT NULL AND center_longitude IS NOT NULL
        AND radius_km IS NOT NULL AND radius_km > 0 AND geometry IS NULL
      WHEN geometry_type = 'polygon' THEN
        geometry IS NOT NULL AND NOT ST_IsEmpty(geometry)
        AND ST_IsValid(geometry) AND ST_Area(geometry::geography) > 0
        AND center_latitude IS NULL AND center_longitude IS NULL
        AND radius_km IS NULL
      ELSE false
    END
    FROM delivery_territories WHERE id = :territory_id
""")
_EXCLUSIONS_VALID = text("""
    SELECT NOT EXISTS (
      SELECT 1 FROM delivery_territory_exclusions
      WHERE territory_id = :territory_id
        AND (ST_IsEmpty(geometry) OR NOT ST_IsValid(geometry))
    )
""")


def inspect_territory_activation_preflight(
    db: Session, territory_id: UUID, *, evaluated_at: datetime | None = None,
) -> TerritoryActivationPreflight | None:
    """Read current draft prerequisites; never grant activation or change checkout.

    A passing report is insufficient to activate coverage. Separate approvals,
    legacy-versus-new parity, payment integration, and rollout gates remain mandatory.
    """
    at = evaluated_at or datetime.now(timezone.utc)
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Evaluation time must be timezone-aware")
    territory = db.get(DeliveryTerritory, territory_id)
    if territory is None:
        return None

    issues: list[str] = []
    if territory.status != "draft":
        issues.append("NOT_DRAFT")
    region = db.get(OperatingRegion, territory.operating_region_id)
    if region is None or region.status != "active":
        issues.append("REGION_NOT_ACTIVE")
    if (
        (territory.effective_from is not None and territory.effective_from > at)
        or (territory.effective_until is not None and territory.effective_until <= at)
    ):
        issues.append("TERRITORY_OUTSIDE_EFFECTIVE_WINDOW")

    if db.execute(_GEOMETRY_VALID, {"territory_id": territory_id}).scalar_one() is not True or (
        db.execute(_EXCLUSIONS_VALID, {"territory_id": territory_id}).scalar_one() is not True
    ):
        issues.append("INVALID_GEOMETRY")

    version = None
    if territory.published_version is None or territory.published_version < 1:
        issues.append("UNPUBLISHED")
    else:
        version = db.scalar(select(DeliveryTerritoryVersion).where(
            DeliveryTerritoryVersion.territory_id == territory_id,
            DeliveryTerritoryVersion.version == territory.published_version,
        ))
        highest = db.scalar(select(func.max(DeliveryTerritoryVersion.version)).where(
            DeliveryTerritoryVersion.territory_id == territory_id,
        ))
        if (
            version is None or version.published_at is None
            or highest != territory.published_version
            or not isinstance(version.snapshot, dict)
            or version.snapshot.get("snapshot_format") != "delivery-geometry-v1"
        ):
            issues.append("INVALID_PUBLICATION_HISTORY")
        elif snapshot_current_territory_geometry(db, territory_id) != version.snapshot:
            issues.append("UNPUBLISHED_GEOMETRY_CHANGES")

    total = db.scalar(select(func.count()).select_from(StoreDeliveryTerritory).where(
        StoreDeliveryTerritory.territory_id == territory_id,
    )) or 0
    eligible = db.scalar(select(func.count()).select_from(StoreDeliveryTerritory)
        .join(Store, Store.id == StoreDeliveryTerritory.store_id)
        .join(Merchant, Merchant.id == Store.merchant_id).where(
        Store.is_active.is_(True),
        Store.delivery_enabled.is_(True),
        Merchant.status == MerchantStatus.APPROVED,
        StoreDeliveryTerritory.territory_id == territory_id,
        StoreDeliveryTerritory.status == "active",
        StoreDeliveryTerritory.delivery_enabled.is_(True),
        (StoreDeliveryTerritory.effective_from.is_(None) | (StoreDeliveryTerritory.effective_from <= at)),
        (StoreDeliveryTerritory.effective_until.is_(None) | (StoreDeliveryTerritory.effective_until > at)),
    )) or 0
    if not eligible:
        issues.append("NO_ELIGIBLE_STORE_ASSIGNMENTS")

    return TerritoryActivationPreflight(
        territory_id=territory_id,
        published_version=territory.published_version,
        total_assignments=total,
        eligible_assignments=eligible,
        issues=tuple(issues),
        technical_checks_passed=not issues,
    )
