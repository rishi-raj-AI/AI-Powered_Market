"""Transactional, draft-only territory snapshot publication.

Publishing records an immutable version and audit event, but deliberately
does NOT activate coverage. Checkout continues using legacy service areas.
Future draft editing/activation endpoints must lock the parent territory row
before touching geometry, exclusions, assignments, or publication state.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.delivery_territories import (
    DeliveryTerritory, DeliveryTerritoryVersion, TerritoryChangeAudit,
)
from app.services.territory_preview import snapshot_current_territory_geometry


class PublicationRejected(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PublicationResult:
    territory_id: UUID
    published_version: int
    status: str


_VALID_SHAPE = text("""
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
    END AS valid
    FROM delivery_territories WHERE id = :territory_id
""")
_INVALID_EXCLUSIONS = text("""
    SELECT count(*) FROM delivery_territory_exclusions
    WHERE territory_id = :territory_id
      AND (ST_IsEmpty(geometry) OR NOT ST_IsValid(geometry))
""")
_LOCK_EXCLUSIONS = text("""
    SELECT id FROM delivery_territory_exclusions
    WHERE territory_id = :territory_id ORDER BY id FOR UPDATE
""")


def publish_initial_draft(
    db: Session,
    *,
    territory_id: UUID,
    actor_id: UUID,
    expected_published_version: int | None,
    reason: str,
) -> PublicationResult:
    """Stage the first immutable published snapshot without activating coverage.

    The caller owns commit/rollback. Locking the parent serializes competing
    publishers; locking existing exclusion rows prevents concurrent edits.
    Future writers must acquire the parent lock as well. A failed operation
    leaves no audit/version rows after the caller rolls back.
    """
    if not reason or len(reason.strip()) < 10 or len(reason) > 500:
        raise PublicationRejected("invalid_reason", "Provide a 10-500 character change reason")

    territory = db.scalar(
        select(DeliveryTerritory)
        .where(DeliveryTerritory.id == territory_id)
        .with_for_update()
    )
    if territory is None:
        raise PublicationRejected("not_found", "Territory not found")
    if territory.published_version != expected_published_version:
        raise PublicationRejected("version_conflict", "Territory publication version changed")
    if territory.status != "draft" or territory.published_version is not None:
        raise PublicationRejected(
            "not_draft", "Only never-published draft territories can be staged",
        )

    db.execute(_LOCK_EXCLUSIONS, {"territory_id": territory_id}).all()
    valid = db.execute(_VALID_SHAPE, {"territory_id": territory_id}).scalar_one()
    if valid is not True:
        raise PublicationRejected("invalid_geometry", "Territory geometry is incomplete or invalid")
    invalid_exclusions = db.execute(
        _INVALID_EXCLUSIONS, {"territory_id": territory_id},
    ).scalar_one()
    if invalid_exclusions:
        raise PublicationRejected("invalid_geometry", "Territory exclusions are invalid")

    # The parent row is locked for the full transaction. Even if another
    # process changes draft geometry after commit, the read-only evaluator
    # fails closed when the live geometry diverges from this snapshot.
    snapshot = snapshot_current_territory_geometry(db, territory_id)
    highest_version = db.scalar(
        select(func.max(DeliveryTerritoryVersion.version))
        .where(DeliveryTerritoryVersion.territory_id == territory_id)
    )
    version = (highest_version or 0) + 1
    now = datetime.now(timezone.utc)
    db.add(DeliveryTerritoryVersion(
        territory_id=territory_id,
        version=version,
        snapshot=snapshot,
        changed_by=actor_id,
        change_reason=reason.strip(),
        published_at=now,
    ))
    db.add(TerritoryChangeAudit(
        territory_id=territory_id,
        actor_id=actor_id,
        action="published",
        previous_version=None,
        new_version=version,
        change_reason=reason.strip(),
        details={"activation": False, "snapshot_format": "delivery-geometry-v1"},
    ))
    territory.published_version = version
    # Intentionally keep status='draft': publishing a snapshot must not
    # activate new store coverage, even if a store assignment exists.
    db.flush()
    return PublicationResult(
        territory_id=territory_id,
        published_version=version,
        status=territory.status,
    )
