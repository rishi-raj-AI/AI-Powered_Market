"""PostGIS-backed address pin provenance and historical-order safety tests."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.routes.geography import confirm_my_address_pin, create_my_address
from app.models.geography import Address
from app.models.orders import PaymentMethod
from app.schemas.geography import AddressCreate, AddressPinConfirm
from tests import factories


def _pin(**changes):
    values = {
        "latitude": 18.5204,
        "longitude": 73.8567,
        "location_source": "map_pin",
    }
    values.update(changes)
    return AddressPinConfirm(**values)


def test_unpinned_legacy_address_can_be_replaced_without_mutating_original():
    with factories.session() as db:
        customer = factories.make_user(db)
        village = factories.make_village(db)
        original = factories.make_address(db, customer, village)
        original.latitude = None
        original.longitude = None
        original.is_default = True
        db.commit()
        old_id = original.id
        old_landmark = original.landmark

        replacement = confirm_my_address_pin(
            old_id, _pin(), db=db, user=customer,
        )
        factories._track(replacement)
        db.refresh(original)
        assert replacement.id != old_id
        assert replacement.location_source == "map_pin"
        assert replacement.location_confirmed_at is not None
        assert replacement.latitude == 18.5204
        assert replacement.longitude == 73.8567
        assert replacement.landmark == old_landmark
        assert replacement.is_default is True
        assert original.archived_at is not None
        assert original.latitude is None and original.longitude is None
        assert original.is_default is False
        db.rollback()


def test_confirming_pin_preserves_order_address_reference_and_snapshot():
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        order = factories.make_order(
            db,
            customer=customer,
            store=store,
            payment_method=PaymentMethod.COD,
            with_paid_attempt=False,
        )
        original_id = order.address_id
        original = db.get(Address, original_id)
        original_snapshot = dict(order.delivery_address)
        db.commit()

        replacement = confirm_my_address_pin(
            original_id, _pin(location_source="gps", location_accuracy_meters=12),
            db=db, user=customer,
        )
        factories._track(replacement)
        db.refresh(order)
        db.refresh(original)
        assert order.address_id == original_id
        assert order.delivery_address == original_snapshot
        assert original.archived_at is not None
        assert original.location_source is None
        assert replacement.location_source == "gps"
        assert replacement.location_accuracy_meters == 12
        db.rollback()


def test_out_of_zone_pin_rejected_without_archiving_original():
    with factories.session() as db:
        customer = factories.make_user(db)
        village = factories.make_village(db)
        original = factories.make_address(db, customer, village)
        db.commit()
        with pytest.raises(HTTPException) as exc:
            confirm_my_address_pin(
                original.id,
                _pin(latitude=0, longitude=0),
                db=db,
                user=customer,
            )
        assert exc.value.status_code == 422
        db.refresh(original)
        assert original.archived_at is None
        assert original.location_source is None
        db.rollback()


def test_customer_cannot_confirm_another_users_address():
    with factories.session() as db:
        owner = factories.make_user(db)
        stranger = factories.make_user(db)
        village = factories.make_village(db)
        original = factories.make_address(db, owner, village)
        db.commit()
        with pytest.raises(HTTPException) as exc:
            confirm_my_address_pin(original.id, _pin(), db=db, user=stranger)
        assert exc.value.status_code == 404
        db.refresh(original)
        assert original.archived_at is None
        db.rollback()


def test_new_address_persists_explicit_provenance_but_legacy_does_not():
    with factories.session() as db:
        customer = factories.make_user(db)
        village = factories.make_village(db)
        created = create_my_address(
            AddressCreate(
                village_id=village.id,
                landmark="Near village school",
                latitude=18.5204,
                longitude=73.8567,
                location_source="gps",
                location_accuracy_meters=14,
            ),
            db=db,
            user=customer,
        )
        factories._track(created)
        assert created.location_source == "gps"
        assert created.location_confirmed_at is not None
        assert created.location_accuracy_meters == 14
        legacy = create_my_address(
            AddressCreate(
                village_id=village.id,
                landmark="Near village school",
                latitude=18.5204,
                longitude=73.8567,
            ),
            db=db,
            user=customer,
        )
        factories._track(legacy)
        assert legacy.location_source is None
        assert legacy.location_confirmed_at is None
        db.rollback()


def test_coordinate_provenance_cannot_be_fabricated_without_coordinates():
    with pytest.raises(ValidationError):
        AddressCreate(
            village_id=uuid4(),
            landmark="Near school",
            location_source="gps",
        )
    with pytest.raises(ValidationError):
        AddressCreate(
            village_id=uuid4(),
            landmark="Near school",
            latitude=18.5204,
        )
    with pytest.raises(ValidationError):
        AddressCreate(
            village_id=uuid4(),
            landmark="Near school",
            location_accuracy_meters=20,
        )
