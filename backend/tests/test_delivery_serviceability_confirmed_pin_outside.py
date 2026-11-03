"""Confirmed customer pins must still obey assigned delivery boundaries.

PostgreSQL/PostGIS integration test with synthetic disposable records only.
"""
from datetime import datetime, timezone

from sqlalchemy import text

from app.db.session import SessionLocal
from app.scripts.diagnose_delivery_serviceability import diagnose
from tests import factories


def test_confirmed_map_pin_outside_assigned_territory_is_rejected():
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        address = factories.make_address(
            db, customer, db.get(factories.Village, store.village_id),
        )
        # Valid but geographically distant pin: confirmation is not coverage.
        address.latitude = 0.0
        address.longitude = 0.0
        address.location_source = "map_pin"
        address.location_confirmed_at = datetime.now(timezone.utc)
        db.commit()

        with SessionLocal() as readonly:
            readonly.execute(text("SET TRANSACTION READ ONLY"))
            result = diagnose(readonly, store.id, address.id)
            assert result["address_inside_assigned_area"] is False
            assert result["serviceable"] is False
            assert result["reason_code"] == "ADDRESS_OUTSIDE_TERRITORY"
            assert result["location_confidence"] == "confirmed_map_pin"
            assert "latitude" not in result and "longitude" not in result
            readonly.rollback()
