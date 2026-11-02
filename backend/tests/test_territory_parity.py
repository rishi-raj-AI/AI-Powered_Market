"""Synthetic PostGIS and HTTP checks for the non-authoritative parity tool."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes import admin_territory_preview
from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.geography import ServiceArea, Village
from app.models.user import UserRole
from app.services.territory_parity import GeographyParity, compare_store_geography
from tests import factories
from tests.test_territory_preview import _active_territory

client = TestClient(app)


def test_parity_detects_expansion_contraction_and_neither():
    with factories.session() as db:
        store = factories.make_store(db, is_active=True)
        _active_territory(db, store)
        # The new synthetic circle is near (0,0); the legacy hub is in Pune.
        expansion = compare_store_geography(db, store.id, 0, 0)
        assert expansion.parity_status == "TERRITORY_ONLY"
        assert expansion.legacy_geographic_match is False
        assert expansion.territory_geographic_match is True
        contraction = compare_store_geography(db, store.id, 18.5204, 73.8567)
        assert contraction.parity_status == "LEGACY_ONLY"
        assert contraction.legacy_geographic_match is True
        assert contraction.territory_geographic_match is False
        neither = compare_store_geography(db, store.id, 40, 40)
        assert neither.parity_status == "NEITHER"
        assert neither.legacy_geographic_match is False
        assert neither.territory_geographic_match is False
        assert not expansion.checkout_authoritative
        assert not expansion.activation_authorized
        db.rollback()


def test_parity_both_match_but_unpublished_geometry_edit_fails_closed():
    with factories.session() as db:
        store = factories.make_store(db, is_active=True)
        hub = db.get(Village, store.village_id)
        hub.latitude, hub.longitude = 0, 0
        _, territory, _ = _active_territory(db, store)
        db.flush()
        both = compare_store_geography(db, store.id, 0, 0)
        assert both.parity_status == "MATCH_BOTH"
        territory.radius_km = 2
        db.flush()
        changed = compare_store_geography(db, store.id, 0, 0)
        assert changed.parity_status == "LEGACY_ONLY"
        db.rollback()


def test_parity_missing_legacy_area_is_not_false_expansion():
    with factories.session() as db:
        store = factories.make_store(db, is_active=True)
        _active_territory(db, store)
        store.service_area_id = None
        db.flush()
        result = compare_store_geography(db, store.id, 0, 0)
        assert result.parity_status == "NOT_COMPARABLE"
        assert result.legacy_geographic_match is None
        assert result.legacy_configuration_issue == "LEGACY_AREA_MISSING"
        assert result.territory_geographic_match is True
        db.rollback()


def test_parity_invalid_legacy_hub_is_not_false_expansion():
    with factories.session() as db:
        store = factories.make_store(db, is_active=True)
        _active_territory(db, store)
        hub = db.get(Village, store.village_id)
        hub.latitude = None
        db.flush()
        result = compare_store_geography(db, store.id, 0, 0)
        assert result.parity_status == "NOT_COMPARABLE"
        assert result.legacy_configuration_issue == "LEGACY_AREA_INVALID"
        db.rollback()


def test_parity_inactive_store_or_delivery_disabled_is_not_comparable():
    with factories.session() as db:
        store = factories.make_store(db)
        _active_territory(db, store)
        assert compare_store_geography(db, store.id, 0, 0).legacy_configuration_issue == "STORE_UNAVAILABLE"
        store.is_active = True
        store.delivery_enabled = False
        db.flush()
        assert compare_store_geography(db, store.id, 0, 0).legacy_configuration_issue == "STORE_DELIVERY_DISABLED"
        db.rollback()


@pytest.mark.parametrize("latitude,longitude", [
    (91, 0), (0, -181), (float("nan"), 0), (0, float("inf")),
])
def test_parity_invalid_coordinates_rejected_before_query(latitude, longitude):
    with factories.session() as db:
        with pytest.raises(ValueError, match="coordinates"):
            compare_store_geography(db, uuid4(), latitude, longitude)


def test_parity_missing_store():
    with factories.session() as db:
        assert compare_store_geography(db, uuid4(), 0, 0) is None


@pytest.fixture
def users():
    with SessionLocal() as db:
        admin = factories.make_user(db, role=UserRole.ADMIN)
        customer = factories.make_user(db, role=UserRole.CUSTOMER)
        db.commit()
        return str(admin.id), str(customer.id)


def _post(user_id=None, *, latitude=0, longitude=0):
    headers = {"Authorization": f"Bearer {create_access_token(user_id)}"} if user_id else {}
    return client.post(
        "/api/v1/admin/delivery-territories/parity-preview",
        headers=headers,
        json={"store_id": str(uuid4()), "latitude": latitude, "longitude": longitude},
    )


def test_parity_api_requires_flag_and_geography_permission(monkeypatch, users):
    admin_id, customer_id = users
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PREVIEW_ENABLED", False)
    assert _post(admin_id).status_code == 404
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PREVIEW_ENABLED", True)
    assert _post().status_code == 401
    assert _post(customer_id).status_code == 403
    assert _post(admin_id).status_code == 404
    assert _post(admin_id, latitude=91).status_code == 422


def test_parity_api_never_returns_test_point_or_authorizes_checkout(monkeypatch, users):
    admin_id, _ = users
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PREVIEW_ENABLED", True)
    monkeypatch.setattr(
        admin_territory_preview, "compare_store_geography",
        lambda db, sid, lat, lon: GeographyParity(
            store_id=sid, legacy_geographic_match=False,
            territory_geographic_match=True, parity_status="TERRITORY_ONLY",
        ),
    )
    response = _post(admin_id, latitude=19.5, longitude=73.9)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parity_status"] == "TERRITORY_ONLY"
    assert body["checkout_authoritative"] is False
    assert body["activation_authorized"] is False
    assert "latitude" not in response.text
    assert "longitude" not in response.text
    assert "19.5" not in response.text
    assert "73.9" not in response.text
