"""PostGIS and API regressions for non-authoritative published draft impact."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes import admin_territory_preview
from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.geography import Village
from app.models.user import UserRole
from app.services.territory_draft_impact import (
    DraftImpact, compare_published_draft_geography,
)
from tests import factories
from tests.test_territory_preview import _active_territory

client = TestClient(app)


def _draft(db, store, *, kind="circle"):
    _, territory, assignment = _active_territory(db, store, kind=kind)
    territory.status = "draft"
    db.flush()
    return territory, assignment


def test_published_draft_detects_expansion_contraction_and_neither():
    with factories.session() as db:
        store = factories.make_store(db, is_active=True)
        territory, _ = _draft(db, store)
        def impact(lat, lon):
            return compare_published_draft_geography(
                db, store_id=store.id, territory_id=territory.id,
                latitude=lat, longitude=lon,
            )
        expansion = impact(0, 0)
        assert expansion.parity_status == "DRAFT_ONLY"
        assert expansion.draft_geographic_match is True
        assert expansion.legacy_geographic_match is False
        contraction = impact(18.5204, 73.8567)
        assert contraction.parity_status == "LEGACY_ONLY"
        assert contraction.draft_geographic_match is False
        assert impact(40, 40).parity_status == "NEITHER"
        assert not expansion.checkout_authoritative
        assert not expansion.activation_authorized
        db.rollback()


def test_draft_polygon_exclusion_and_boundary_are_respected():
    with factories.session() as db:
        store = factories.make_store(db, is_active=True)
        territory, _ = _draft(db, store, kind="polygon")
        def match(lat, lon):
            return compare_published_draft_geography(
                db, store_id=store.id, territory_id=territory.id,
                latitude=lat, longitude=lon,
            ).draft_geographic_match
        assert match(0.0, 0.5) is True
        assert match(0.5, 0.5) is False
        assert match(0.4, 0.5) is False
        db.rollback()


def test_unpublished_draft_edit_fails_closed_instead_of_false_contraction():
    with factories.session() as db:
        store = factories.make_store(db, is_active=True)
        territory, _ = _draft(db, store)
        territory.radius_km = 2
        db.flush()
        result = compare_published_draft_geography(
            db, store_id=store.id, territory_id=territory.id,
            latitude=0, longitude=0,
        )
        assert result.parity_status == "NOT_COMPARABLE"
        assert result.draft_geographic_match is None
        assert result.draft_issue == "UNPUBLISHED_GEOMETRY_CHANGES"
        db.rollback()


def test_missing_or_inactive_assignment_is_not_false_contraction():
    with factories.session() as db:
        store = factories.make_store(db, is_active=True)
        territory, assignment = _draft(db, store)
        assignment.delivery_enabled = False
        db.flush()
        result = compare_published_draft_geography(
            db, store_id=store.id, territory_id=territory.id,
            latitude=18.5204, longitude=73.8567,
        )
        assert result.parity_status == "NOT_COMPARABLE"
        assert result.draft_issue == "ASSIGNMENT_NOT_ELIGIBLE"
        other = factories.make_store(db, is_active=True)
        other_result = compare_published_draft_geography(
            db, store_id=other.id, territory_id=territory.id,
            latitude=0, longitude=0,
        )
        assert other_result.draft_issue == "STORE_NOT_ASSIGNED"
        db.rollback()


def test_invalid_legacy_configuration_is_not_false_expansion():
    with factories.session() as db:
        store = factories.make_store(db, is_active=True)
        territory, _ = _draft(db, store)
        hub = db.get(Village, store.village_id)
        hub.latitude = None
        db.flush()
        result = compare_published_draft_geography(
            db, store_id=store.id, territory_id=territory.id,
            latitude=0, longitude=0,
        )
        assert result.parity_status == "NOT_COMPARABLE"
        assert result.legacy_geographic_match is None
        assert result.legacy_configuration_issue == "LEGACY_AREA_INVALID"
        db.rollback()


def test_active_territory_is_not_misreported_as_draft():
    with factories.session() as db:
        store = factories.make_store(db, is_active=True)
        _, territory, _ = _active_territory(db, store)
        result = compare_published_draft_geography(
            db, store_id=store.id, territory_id=territory.id,
            latitude=0, longitude=0,
        )
        assert result.draft_issue == "TERRITORY_NOT_DRAFT"
        assert result.draft_geographic_match is None
        db.rollback()


@pytest.mark.parametrize("lat,lon", [
    (91, 0), (0, -181), (float("nan"), 0), (0, float("inf")),
])
def test_invalid_coordinates_rejected(lat, lon):
    with factories.session() as db:
        with pytest.raises(ValueError, match="coordinates"):
            compare_published_draft_geography(
                db, store_id=uuid4(), territory_id=uuid4(),
                latitude=lat, longitude=lon,
            )


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
        "/api/v1/admin/delivery-territories/draft-impact-preview",
        headers=headers,
        json={
            "store_id": str(uuid4()), "territory_id": str(uuid4()),
            "latitude": latitude, "longitude": longitude,
        },
    )


def test_api_flag_permission_and_coordinate_validation(monkeypatch, users):
    admin_id, customer_id = users
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PREVIEW_ENABLED", False)
    assert _post(admin_id).status_code == 404
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PREVIEW_ENABLED", True)
    assert _post().status_code == 401
    assert _post(customer_id).status_code == 403
    assert _post(admin_id).status_code == 404
    assert _post(admin_id, latitude=91).status_code == 422


def test_api_excludes_point_and_cannot_authorize_checkout(monkeypatch, users):
    admin_id, _ = users
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PREVIEW_ENABLED", True)
    monkeypatch.setattr(
        admin_territory_preview, "compare_published_draft_geography",
        lambda db, **kwargs: DraftImpact(
            store_id=kwargs["store_id"], territory_id=kwargs["territory_id"],
            published_version=2, legacy_geographic_match=False,
            draft_geographic_match=True, parity_status="DRAFT_ONLY",
        ),
    )
    response = _post(admin_id, latitude=19.5, longitude=73.9)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parity_status"] == "DRAFT_ONLY"
    assert body["checkout_authoritative"] is False
    assert body["activation_authorized"] is False
    assert "latitude" not in response.text
    assert "longitude" not in response.text
    assert "19.5" not in response.text
    assert "73.9" not in response.text
