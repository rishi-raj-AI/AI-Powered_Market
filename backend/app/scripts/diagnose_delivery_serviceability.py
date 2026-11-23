"""Read-only, narrowly scoped PostGIS checkout diagnosis.

Usage (from backend/):
  python -m app.scripts.diagnose_delivery_serviceability \
    --store-id UUID --address-id UUID --acknowledge-authorized-access

Only IDs, configuration flags, decisions and rounded distances are emitted.
Never prints names, phones, landmarks, house details or exact coordinates.
Run with a database account restricted to SELECT wherever possible.
"""

import argparse
import json
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.commerce import Store
from app.models.geography import Address
from app.services.delivery_serviceability import evaluate_delivery


DIAGNOSTIC_SQL = text("""
SELECT
    s.is_active AS store_active,
    s.delivery_enabled,
    m.status::text AS merchant_status,
    s.service_area_id,
    sa.is_active AS territory_active,
    v.is_active AS hub_active,
    sa.radius_km,
    (s.latitude IS NOT NULL AND s.longitude IS NOT NULL) AS store_pin_present,
    (a.latitude IS NOT NULL AND a.longitude IS NOT NULL) AS address_pin_present,
    (av.latitude IS NOT NULL AND av.longitude IS NOT NULL) AS locality_reference_present,
    CASE WHEN
        a.latitude BETWEEN -90 AND 90 AND a.longitude BETWEEN -180 AND 180
        AND s.latitude BETWEEN -90 AND 90 AND s.longitude BETWEEN -180 AND 180
    THEN ROUND((
        ST_Distance(
            ST_SetSRID(ST_MakePoint(s.longitude::double precision, s.latitude::double precision), 4326)::geography,
            ST_SetSRID(ST_MakePoint(a.longitude::double precision, a.latitude::double precision), 4326)::geography
        ) / 1000.0
    )::numeric, 3) END AS store_to_address_km,
    CASE WHEN
        a.latitude BETWEEN -90 AND 90 AND a.longitude BETWEEN -180 AND 180
        AND v.latitude BETWEEN -90 AND 90 AND v.longitude BETWEEN -180 AND 180
    THEN ROUND((
        ST_Distance(
            ST_SetSRID(ST_MakePoint(v.longitude::double precision, v.latitude::double precision), 4326)::geography,
            ST_SetSRID(ST_MakePoint(a.longitude::double precision, a.latitude::double precision), 4326)::geography
        ) / 1000.0
    )::numeric, 3) END AS hub_to_address_km,
    CASE WHEN
        sa.is_active AND v.is_active AND sa.radius_km > 0
        AND a.latitude BETWEEN -90 AND 90 AND a.longitude BETWEEN -180 AND 180
        AND v.latitude BETWEEN -90 AND 90 AND v.longitude BETWEEN -180 AND 180
    THEN ST_DWithin(
        ST_SetSRID(ST_MakePoint(v.longitude::double precision, v.latitude::double precision), 4326)::geography,
        ST_SetSRID(ST_MakePoint(a.longitude::double precision, a.latitude::double precision), 4326)::geography,
        sa.radius_km * 1000.0
    ) ELSE false END AS address_inside_assigned_area,
    CASE WHEN
        sa.is_active AND v.is_active AND sa.radius_km > 0
        AND s.latitude BETWEEN -90 AND 90 AND s.longitude BETWEEN -180 AND 180
        AND v.latitude BETWEEN -90 AND 90 AND v.longitude BETWEEN -180 AND 180
    THEN ST_DWithin(
        ST_SetSRID(ST_MakePoint(v.longitude::double precision, v.latitude::double precision), 4326)::geography,
        ST_SetSRID(ST_MakePoint(s.longitude::double precision, s.latitude::double precision), 4326)::geography,
        sa.radius_km * 1000.0
    ) ELSE false END AS store_inside_assigned_area,
    CASE WHEN
        (a.latitude IS NULL OR a.longitude IS NULL)
        AND sa.is_active AND v.is_active AND sa.radius_km > 0
        AND av.latitude BETWEEN -90 AND 90 AND av.longitude BETWEEN -180 AND 180
        AND v.latitude BETWEEN -90 AND 90 AND v.longitude BETWEEN -180 AND 180
    THEN ST_DWithin(
        ST_SetSRID(ST_MakePoint(v.longitude::double precision, v.latitude::double precision), 4326)::geography,
        ST_SetSRID(ST_MakePoint(av.longitude::double precision, av.latitude::double precision), 4326)::geography,
        sa.radius_km * 1000.0
    ) ELSE false END AS legacy_locality_fallback_inside_area
FROM stores s
JOIN addresses a ON a.id = CAST(:address_id AS uuid)
LEFT JOIN merchants m ON m.id = s.merchant_id
LEFT JOIN service_areas sa ON sa.id = s.service_area_id
LEFT JOIN villages v ON v.id = sa.hub_village_id
LEFT JOIN villages av ON av.id = a.village_id
WHERE s.id = CAST(:store_id AS uuid)
""")


def diagnose(db: Session, store_id: uuid.UUID, address_id: uuid.UUID) -> dict:
    """The caller must start a read-only transaction before invoking this."""
    store = db.get(Store, store_id)
    address = db.get(Address, address_id)
    if store is None or address is None:
        return {"store_id": str(store_id), "address_id": str(address_id), "found": False}
    row = db.execute(
        DIAGNOSTIC_SQL, {"store_id": store_id, "address_id": address_id}
    ).mappings().one()
    decision = evaluate_delivery(db, store, address)
    safe_fields = (
        "store_active", "delivery_enabled", "merchant_status",
        "territory_active", "hub_active", "radius_km",
        "store_pin_present", "address_pin_present",
        "locality_reference_present", "store_to_address_km",
        "hub_to_address_km", "address_inside_assigned_area",
        "store_inside_assigned_area", "legacy_locality_fallback_inside_area",
    )
    result = {key: row[key] for key in safe_fields}
    # Round distance/fee values already returned by PostGIS; never emit points.
    for key in ("radius_km", "store_to_address_km", "hub_to_address_km"):
        result[key] = float(result[key]) if result[key] is not None else None
    result.update({
        "store_id": str(store_id),
        "address_id": str(address_id),
        "service_area_id": str(row["service_area_id"]) if row["service_area_id"] else None,
        "found": True,
        "serviceable": decision.serviceable,
        "reason_code": decision.reason_code,
        "evaluation_version": decision.evaluation_version,
        "location_confidence": decision.location_confidence,
        "village_fallback_would_be_used_by_old_checkout": (
            not result["address_pin_present"] and result["locality_reference_present"]
        ),
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only scoped delivery diagnosis")
    parser.add_argument("--store-id", type=uuid.UUID, required=True)
    parser.add_argument("--address-id", type=uuid.UUID, required=True)
    parser.add_argument(
        "--acknowledge-authorized-access", action="store_true",
        help="Confirm operator authorization for this specific store/address pair",
    )
    args = parser.parse_args()
    if not args.acknowledge_authorized_access:
        parser.error("Explicit --acknowledge-authorized-access is required")
    with SessionLocal() as db:
        try:
            # PostgreSQL rejects all INSERT/UPDATE/DELETE in this transaction.
            db.execute(text("SET TRANSACTION READ ONLY"))
            result = diagnose(db, args.store_id, args.address_id)
            print(json.dumps(result, sort_keys=True, indent=2))
        finally:
            db.rollback()


if __name__ == "__main__":
    main()
