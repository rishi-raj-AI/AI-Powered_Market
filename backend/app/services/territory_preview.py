"""Read-only PostGIS preview of *active* store-assigned delivery territories.

This is NOT the checkout authority. Legacy service_areas continue to decide
checkout until backfill, comparison-mode parity, and a reviewed feature switch.
No customer coordinates or personal address details are logged.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class TerritoryMatch:
    territory_id: UUID
    assignment_id: UUID
    geometry_type: str
    territory_priority: int
    assignment_priority: int


# For geometry, longitude is X and latitude is Y. For circles, geography
# gives geodesic metre distances rather than planar degree distances.
_POINT = "ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)"

# Publication must capture this exact, canonical geometry/exclusion snapshot.
# An unpublished edit to mutable draft geometry must never silently affect
# a published geographic preview. This is a fail-closed comparison, not an
# authoritative checkout engine or a publication endpoint.
_EXCLUSIONS_JSON = """
    COALESCE((
        SELECT jsonb_agg(encode(ST_AsEWKB(e.geometry), 'hex') ORDER BY e.id)
        FROM delivery_territory_exclusions e
        WHERE e.territory_id = t.id
    ), '[]'::jsonb)
"""
_SNAPSHOT_JSON = f"""
    jsonb_build_object(
        'snapshot_format', 'delivery-geometry-v1',
        'geometry_type', t.geometry_type,
        'center_latitude', t.center_latitude::text,
        'center_longitude', t.center_longitude::text,
        'radius_km', t.radius_km::text,
        'geometry_hex', encode(ST_AsEWKB(t.geometry), 'hex'),
        'exclusion_hex', {_EXCLUSIONS_JSON}
    )
"""
_SNAPSHOT_SQL = text(f"""
    SELECT {_SNAPSHOT_JSON} AS snapshot
    FROM delivery_territories t
    WHERE t.id = :territory_id
""")
_SQL = text(f"""
    SELECT
        t.id AS territory_id,
        a.id AS assignment_id,
        t.geometry_type,
        t.priority AS territory_priority,
        a.priority AS assignment_priority
    FROM store_delivery_territories a
    JOIN delivery_territories t ON t.id = a.territory_id
    JOIN operating_regions r ON r.id = t.operating_region_id
    WHERE a.store_id = :store_id
      AND a.status = 'active'
      AND a.delivery_enabled = true
      AND t.status = 'active'
      AND r.status = 'active'
      AND t.published_version IS NOT NULL
      AND EXISTS (
        SELECT 1 FROM delivery_territory_versions v
        WHERE v.territory_id = t.id
          AND v.version = t.published_version
          AND v.published_at IS NOT NULL
          AND v.snapshot = {_SNAPSHOT_JSON}
      )
      AND (a.effective_from IS NULL OR a.effective_from <= :evaluated_at)
      AND (a.effective_until IS NULL OR a.effective_until > :evaluated_at)
      AND (t.effective_from IS NULL OR t.effective_from <= :evaluated_at)
      AND (t.effective_until IS NULL OR t.effective_until > :evaluated_at)
      AND (
        (
          t.geometry_type = 'circle'
          AND t.center_latitude IS NOT NULL
          AND t.center_longitude IS NOT NULL
          AND t.radius_km > 0
          AND ST_DWithin(
            ST_SetSRID(ST_MakePoint(
              t.center_longitude::double precision,
              t.center_latitude::double precision
            ), 4326)::geography,
            {_POINT}::geography,
            t.radius_km::double precision * 1000.0
          )
        )
        OR (
          t.geometry_type = 'polygon'
          AND t.geometry IS NOT NULL
          AND ST_Covers(t.geometry, {_POINT})
        )
      )
      AND NOT EXISTS (
        SELECT 1 FROM delivery_territory_exclusions e
        WHERE e.territory_id = t.id
          AND ST_Covers(e.geometry, {_POINT})
      )
    ORDER BY a.priority DESC, t.priority DESC, t.id ASC, a.id ASC
    LIMIT 1
""")


def snapshot_current_territory_geometry(
    db: Session, territory_id: UUID,
) -> dict[str, object]:
    """Read the canonical geometry snapshot for a future audited publisher.

    This does not publish, mutate, or authorize a territory. The publisher
    must capture it transactionally with appropriate locks and approval.
    """
    row = db.execute(
        _SNAPSHOT_SQL, {"territory_id": territory_id},
    ).mappings().first()
    if row is None:
        raise ValueError("Territory does not exist")
    return row["snapshot"]


def match_active_store_territory(
    db: Session,
    store_id: UUID,
    latitude: float,
    longitude: float,
    *,
    evaluated_at: datetime | None = None,
) -> TerritoryMatch | None:
    """Find one eligible *geographic* match, without claiming fulfilment.

    Only explicitly active store assignments and territories qualify. An
    empty result is not a checkout rejection: legacy coverage remains
    authoritative, and this function does not check merchant approval,
    inventory, pricing, partner availability, or payment.
    """
    if not all(isfinite(v) for v in (latitude, longitude)):
        raise ValueError("Location coordinates must be finite")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Location coordinates are outside WGS84 bounds")
    if evaluated_at is None:
        evaluated_at = datetime.now(timezone.utc)
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("Evaluation time must be timezone-aware")
    row = db.execute(
        _SQL,
        {
            "store_id": store_id,
            "latitude": float(latitude),
            "longitude": float(longitude),
            "evaluated_at": evaluated_at,
        },
    ).mappings().first()
    return TerritoryMatch(**dict(row)) if row else None
