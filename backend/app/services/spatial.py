import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session


POINT_SQL = "ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography"


def serviceability_for_point(db: Session, latitude: float, longitude: float) -> dict | None:
    row = db.execute(
        text(
            """
            SELECT
                sa.id,
                sa.name,
                sa.radius_km,
                ST_Distance(
                    ST_SetSRID(ST_MakePoint(v.longitude::double precision, v.latitude::double precision), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
                ) / 1000.0 AS distance_km
            FROM service_areas sa
            JOIN villages v ON v.id = sa.hub_village_id
            WHERE sa.is_active = true
              AND v.is_active = true
              AND v.latitude IS NOT NULL
              AND v.longitude IS NOT NULL
            ORDER BY
                ST_SetSRID(ST_MakePoint(v.longitude::double precision, v.latitude::double precision), 4326)::geography
                <-> ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
            LIMIT 1
            """
        ),
        {"latitude": latitude, "longitude": longitude},
    ).mappings().first()
    return dict(row) if row else None


def point_is_in_service_area(
    db: Session,
    service_area_id: uuid.UUID,
    latitude: float,
    longitude: float,
) -> bool:
    return bool(
        db.scalar(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM service_areas sa
                    JOIN villages v ON v.id = sa.hub_village_id
                    WHERE sa.id = :service_area_id
                      AND sa.is_active = true
                      AND v.is_active = true
                      AND v.latitude IS NOT NULL
                      AND v.longitude IS NOT NULL
                      AND ST_DWithin(
                          ST_SetSRID(ST_MakePoint(v.longitude::double precision, v.latitude::double precision), 4326)::geography,
                          ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography,
                          sa.radius_km * 1000.0
                      )
                )
                """
            ),
            {
                "service_area_id": service_area_id,
                "latitude": latitude,
                "longitude": longitude,
            },
        )
    )


def nearby_store_distances(
    db: Session,
    latitude: float,
    longitude: float,
    radius_km: float,
    delivery: bool | None = None,
) -> list[tuple[uuid.UUID, float]]:
    rows = db.execute(
        text(
            """
            SELECT
                s.id,
                ST_Distance(
                    ST_SetSRID(ST_MakePoint(s.longitude::double precision, s.latitude::double precision), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
                ) / 1000.0 AS distance_km
            FROM stores s
            JOIN merchants m ON m.id = s.merchant_id
            WHERE s.is_active = true
              AND m.status = 'approved'
              AND s.latitude IS NOT NULL
              AND s.longitude IS NOT NULL
              AND (CAST(:delivery AS boolean) IS NULL OR s.delivery_enabled = CAST(:delivery AS boolean))
              AND ST_DWithin(
                  ST_SetSRID(ST_MakePoint(s.longitude::double precision, s.latitude::double precision), 4326)::geography,
                  ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography,
                  :radius_m
              )
            ORDER BY
                ST_SetSRID(ST_MakePoint(s.longitude::double precision, s.latitude::double precision), 4326)::geography
                <-> ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
            """
        ),
        {
            "latitude": latitude,
            "longitude": longitude,
            "radius_m": radius_km * 1000.0,
            "delivery": delivery,
        },
    ).all()
    return [(row[0], float(row[1])) for row in rows]


def nearest_eligible_rider(
    db: Session,
    store_latitude: float,
    store_longitude: float,
    max_radius_km: float,
) -> tuple[uuid.UUID, float] | None:
    row = db.execute(
        text(
            """
            SELECT
                u.id,
                ST_Distance(
                    ST_SetSRID(ST_MakePoint(rp.longitude::double precision, rp.latitude::double precision), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(:store_longitude, :store_latitude), 4326)::geography
                ) / 1000.0 AS distance_km
            FROM users u
            JOIN rider_presences rp ON rp.rider_id = u.id
            WHERE u.role = 'delivery'
              AND u.is_active = true
              AND u.is_verified = true
              AND rp.is_online = true
              AND rp.last_seen_at >= NOW() - INTERVAL '5 minutes'
              AND ST_DWithin(
                  ST_SetSRID(ST_MakePoint(rp.longitude::double precision, rp.latitude::double precision), 4326)::geography,
                  ST_SetSRID(ST_MakePoint(:store_longitude, :store_latitude), 4326)::geography,
                  :radius_m
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM deliveries d
                  WHERE d.delivery_partner_id = u.id
                    AND d.status IN ('assigned', 'picked_up')
              )
            ORDER BY
                ST_SetSRID(ST_MakePoint(rp.longitude::double precision, rp.latitude::double precision), 4326)::geography
                <-> ST_SetSRID(ST_MakePoint(:store_longitude, :store_latitude), 4326)::geography
            FOR UPDATE OF u SKIP LOCKED
            LIMIT 1
            """
        ),
        {
            "store_latitude": store_latitude,
            "store_longitude": store_longitude,
            "radius_m": max_radius_km * 1000.0,
        },
    ).first()
    if row is None:
        return None
    return row[0], float(row[1])
