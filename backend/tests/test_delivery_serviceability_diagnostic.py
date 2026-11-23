"""Scoped read-only diagnosis acceptance on the combined payment/geography branch.

Uses disposable synthetic test data. No live addresses or production access.
"""
from uuid import uuid4

from sqlalchemy import text

from app.db.session import SessionLocal
from app.scripts.diagnose_delivery_serviceability import diagnose
from tests import factories


def test_scoped_diagnostic_reports_decision_without_personal_or_precise_location():
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        address = factories.make_address(
            db, customer, db.get(factories.Village, store.village_id),
        )
        db.commit()
        with SessionLocal() as readonly:
            readonly.execute(text("SET TRANSACTION READ ONLY"))
            assert readonly.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
            result = diagnose(readonly, store.id, address.id)
            assert result["found"] is True
            assert result["store_id"] == str(store.id)
            assert result["address_id"] == str(address.id)
            assert result["service_area_id"] == str(store.service_area_id)
            assert isinstance(result["serviceable"], bool)
            assert isinstance(result["reason_code"], str)
            assert result["address_pin_present"] is True
            assert result["hub_to_address_km"] is not None
            assert set(result).isdisjoint({
                "recipient_name", "phone", "house_details", "landmark",
                "latitude", "longitude", "customer_id", "place_id",
            })
            readonly.rollback()


def test_unpinned_address_is_not_mistaken_for_confirmed_doorstep():
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        address = factories.make_address(
            db, customer, db.get(factories.Village, store.village_id),
        )
        address.latitude = None
        address.longitude = None
        db.commit()
        with SessionLocal() as readonly:
            readonly.execute(text("SET TRANSACTION READ ONLY"))
            result = diagnose(readonly, store.id, address.id)
            assert result["found"] is True
            assert result["address_pin_present"] is False
            assert result["village_fallback_would_be_used_by_old_checkout"] is True
            assert result["serviceable"] is False
            assert result["reason_code"] == "ADDRESS_COORDINATES_MISSING"
            readonly.rollback()


def test_unknown_scoped_pair_returns_no_customer_details():
    with SessionLocal() as readonly:
        readonly.execute(text("SET TRANSACTION READ ONLY"))
        result = diagnose(readonly, uuid4(), uuid4())
        assert result["found"] is False
        assert set(result) == {"store_id", "address_id", "found"}
        readonly.rollback()


def test_scoped_diagnostic_fails_closed_for_approximate_searched_place():
    """A searched place inside the hub radius is not a confirmed doorstep pin."""
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        address = factories.make_address(
            db, customer, db.get(factories.Village, store.village_id),
        )
        address.location_source = "searched_place"
        db.commit()
        with SessionLocal() as readonly:
            readonly.execute(text("SET TRANSACTION READ ONLY"))
            result = diagnose(readonly, store.id, address.id)
            assert result["address_inside_assigned_area"] is True
            assert result["serviceable"] is False
            assert result["reason_code"] == "ADDRESS_LOCATION_UNCONFIRMED"
            assert result["location_confidence"] == "approximate_searched_place"
            assert "latitude" not in result and "longitude" not in result
            readonly.rollback()


def test_scoped_diagnostic_fails_closed_for_unconfirmed_gps_pin():
    """A GPS label without a server confirmation timestamp cannot authorize delivery."""
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        address = factories.make_address(
            db, customer, db.get(factories.Village, store.village_id),
        )
        address.location_source = "gps"
        address.location_confirmed_at = None
        db.commit()
        with SessionLocal() as readonly:
            readonly.execute(text("SET TRANSACTION READ ONLY"))
            result = diagnose(readonly, store.id, address.id)
            assert result["address_inside_assigned_area"] is True
            assert result["serviceable"] is False
            assert result["reason_code"] == "ADDRESS_LOCATION_UNCONFIRMED"
            assert result["location_confidence"] == "unconfirmed_gps"
            readonly.rollback()
