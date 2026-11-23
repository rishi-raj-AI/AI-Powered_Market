"""P0 regression: legacy compatibility must not bypass territory boundaries.

Uses disposable synthetic PostgreSQL/PostGIS fixtures only.
"""
from sqlalchemy import text

from app.db.session import SessionLocal
from app.scripts.diagnose_delivery_serviceability import diagnose
from tests import factories


def test_legacy_null_provenance_outside_territory_is_rejected():
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        address = factories.make_address(
            db, customer, db.get(factories.Village, store.village_id),
        )
        # Valid coordinates, intentionally far from the Indian test hub.
        # Legacy provenance permits evaluation, never a coverage bypass.
        address.latitude = 0.0
        address.longitude = 0.0
        address.location_source = None
        address.location_confirmed_at = None
        db.commit()
        with SessionLocal() as readonly:
            readonly.execute(text("SET TRANSACTION READ ONLY"))
            result = diagnose(readonly, store.id, address.id)
            assert result["address_inside_assigned_area"] is False
            assert result["serviceable"] is False
            assert result["reason_code"] == "ADDRESS_OUTSIDE_TERRITORY"
            assert result["location_confidence"] == "legacy_coordinates"
            assert "latitude" not in result and "longitude" not in result
            readonly.rollback()
