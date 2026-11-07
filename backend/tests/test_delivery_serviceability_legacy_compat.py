"""P0 compatibility guard: historical coordinates remain distinct from confirmed pins.

Disposable synthetic PostgreSQL/PostGIS data only; never accesses production.
"""
from sqlalchemy import text

from app.db.session import SessionLocal
from app.scripts.diagnose_delivery_serviceability import diagnose
from tests import factories


def test_historical_null_provenance_is_eligible_but_not_confirmed():
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        address = factories.make_address(
            db, customer, db.get(factories.Village, store.village_id),
        )
        address.location_source = None
        address.location_confirmed_at = None
        db.commit()
        with SessionLocal() as readonly:
            readonly.execute(text("SET TRANSACTION READ ONLY"))
            result = diagnose(readonly, store.id, address.id)
            assert result["address_inside_assigned_area"] is True
            assert result["serviceable"] is True
            assert result["reason_code"] == "SERVICEABLE"
            assert result["location_confidence"] == "legacy_coordinates"
            assert "latitude" not in result and "longitude" not in result
            readonly.rollback()


def test_explicit_unconfirmed_map_pin_does_not_inherit_legacy_exception():
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        address = factories.make_address(
            db, customer, db.get(factories.Village, store.village_id),
        )
        address.location_source = "map_pin"
        address.location_confirmed_at = None
        db.commit()
        with SessionLocal() as readonly:
            readonly.execute(text("SET TRANSACTION READ ONLY"))
            result = diagnose(readonly, store.id, address.id)
            assert result["address_inside_assigned_area"] is True
            assert result["serviceable"] is False
            assert result["reason_code"] == "ADDRESS_LOCATION_UNCONFIRMED"
            assert result["location_confidence"] == "unconfirmed_map_pin"
            readonly.rollback()
