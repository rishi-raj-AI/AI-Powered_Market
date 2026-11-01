"""Regression coverage for false negatives at the checkout delivery boundary."""
import uuid
from unittest.mock import Mock

from app.services.spatial import store_delivery_serviceable


def test_store_radius_uses_store_pin_and_active_service_area():
    db = Mock()
    db.scalar.return_value = True
    store_id, area_id = uuid.uuid4(), uuid.uuid4()
    assert store_delivery_serviceable(db, store_id, area_id, 18.63, 73.81)
    query, params = db.scalar.call_args.args[0], db.scalar.call_args.args[1]
    sql = str(query)
    assert "COALESCE(s.longitude" in sql
    assert "COALESCE(s.latitude" in sql
    assert "sa.is_active = true" in sql
    assert "sa.radius_km * 1000.0" in sql
    assert params["store_id"] == store_id
    assert params["service_area_id"] == area_id


def test_serviceability_rejects_outside_radius():
    db = Mock()
    db.scalar.return_value = False
    assert not store_delivery_serviceable(db, uuid.uuid4(), uuid.uuid4(), 18.63, 73.81)
