"""Unconfirmed location provenance cannot authorize checkout.

Synthetic PostgreSQL/PostGIS fixtures only; diagnostic access is read-only.
"""
import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.scripts.diagnose_delivery_serviceability import diagnose
from tests import factories


@pytest.mark.parametrize(
    ("source", "expected_confidence"),
    [
        ("gps", "unconfirmed_gps"),
        ("map_pin", "unconfirmed_map_pin"),
        ("searched_place", "approximate_searched_place"),
        ("unknown_provider", "unrecognized_location_source"),
    ],
)
def test_unconfirmed_location_source_is_not_checkout_eligible(source, expected_confidence):
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        address = factories.make_address(
            db, customer, db.get(factories.Village, store.village_id),
        )
        address.latitude = 0.0
        address.longitude = 0.0
        address.location_source = source
        address.location_confirmed_at = None
        db.commit()

        with SessionLocal() as readonly:
            readonly.execute(text("SET TRANSACTION READ ONLY"))
            result = diagnose(readonly, store.id, address.id)
            assert result["serviceable"] is False
            assert result["reason_code"] == "ADDRESS_LOCATION_UNCONFIRMED"
            assert result["location_confidence"] == expected_confidence
            assert "latitude" not in result and "longitude" not in result
            readonly.rollback()
