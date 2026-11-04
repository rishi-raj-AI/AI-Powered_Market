"""Confirmed in-territory pins and historical coordinates remain eligible.

Disposable PostgreSQL/PostGIS fixtures; diagnosis uses a read-only transaction.
This is a positive counterpart to outside-territory and unconfirmed-pin tests.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.scripts.diagnose_delivery_serviceability import diagnose
from tests import factories


@pytest.mark.parametrize(
    ("source", "confirmed", "expected_confidence"),
    [
        ("gps", True, "confirmed_gps"),
        ("map_pin", True, "confirmed_map_pin"),
        (None, False, "legacy_coordinates"),
    ],
)
def test_in_territory_confirmed_or_legacy_location_is_serviceable(
    source, confirmed, expected_confidence,
):
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        village = db.get(factories.Village, store.village_id)
        address = factories.make_address(db, customer, village)
        # Exactly at the configured hub, not merely near the store pin.
        address.latitude = village.latitude
        address.longitude = village.longitude
        address.location_source = source
        address.location_confirmed_at = (
            datetime.now(timezone.utc) if confirmed else None
        )
        db.commit()

        with SessionLocal() as readonly:
            readonly.execute(text("SET TRANSACTION READ ONLY"))
            result = diagnose(readonly, store.id, address.id)
            assert result["found"] is True
            assert result["address_inside_assigned_area"] is True
            assert result["serviceable"] is True
            assert result["reason_code"] == "SERVICEABLE"
            assert result["location_confidence"] == expected_confidence
            assert result["service_area_id"] == str(store.service_area_id)
            assert "latitude" not in result and "longitude" not in result
            readonly.rollback()
