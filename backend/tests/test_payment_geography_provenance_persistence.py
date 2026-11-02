"""Cross-branch persistence regression: serviceability must read persisted provenance."""
from app.models.geography import Address
from app.services.delivery_serviceability import evaluate_delivery
from tests import factories


def test_persisted_searched_place_cannot_be_treated_as_legacy_pin():
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        village = db.get(factories.Village, store.village_id)
        address = factories.make_address(db, customer, village)
        address.location_source = "searched_place"
        address.location_confirmed_at = None
        db.commit()
        db.expire_all()
        persisted = db.get(Address, address.id)
        assert persisted.location_source == "searched_place"
        decision = evaluate_delivery(db, store, persisted)
        assert decision.reason_code == "ADDRESS_LOCATION_UNCONFIRMED"
        assert decision.location_confidence == "approximate_searched_place"
        db.rollback()


def test_persisted_confirmed_pin_is_distinct_from_legacy_coordinates():
    from datetime import datetime, timezone

    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        village = db.get(factories.Village, store.village_id)
        address = factories.make_address(db, customer, village)
        address.location_source = "map_pin"
        address.location_confirmed_at = datetime.now(timezone.utc)
        db.commit()
        db.expire_all()
        persisted = db.get(Address, address.id)
        decision = evaluate_delivery(db, store, persisted)
        assert decision.location_confidence == "confirmed_map_pin"
        assert decision.reason_code == "SERVICEABLE"
        db.rollback()
