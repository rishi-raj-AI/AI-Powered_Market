"""Synthetic PostGIS and HTTP regressions for read-only activation preflight."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes import admin_territory_preview
from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.delivery_territories import (
    DeliveryTerritory, OperatingRegion, StoreDeliveryTerritory,
)
from app.models.user import UserRole
from app.services.territory_activation_preflight import (
    TerritoryActivationPreflight, inspect_territory_activation_preflight,
)
from app.services.territory_publication import publish_initial_draft
from tests import factories

client = TestClient(app)


def _draft(db):
    region = OperatingRegion(
        name="Synthetic readiness region",
        slug=f"readiness-{uuid4().hex}",
        status="active",
    )
    db.add(region)
    db.flush()
    territory = DeliveryTerritory(
        operating_region_id=region.id, name="Synthetic readiness circle",
        geometry_type="circle", center_latitude=0, center_longitude=0,
        radius_km=1, status="draft",
    )
    actor = factories.make_user(db)
    db.add(territory)
    db.flush()
    return region, territory, actor


def _publish(db, territory, actor):
    publish_initial_draft(
        db, territory_id=territory.id, actor_id=actor.id,
        expected_published_version=None,
        reason="Reviewed synthetic readiness snapshot",
    )


def test_preflight_never_activates_or_authorizes_checkout():
    with factories.session() as db:
        _, territory, actor = _draft(db)
        _publish(db, territory, actor)
        store = factories.make_store(db, is_active=True)
        db.add(StoreDeliveryTerritory(
            store_id=store.id, territory_id=territory.id,
            status="active", delivery_enabled=True,
        ))
        db.flush()
        report = inspect_territory_activation_preflight(db, territory.id)
        assert report.technical_checks_passed is True
        assert report.issues == ()
        assert report.total_assignments == 1
        assert report.eligible_assignments == 1
        assert report.activation_authorized is False
        assert report.checkout_authoritative is False
        assert territory.status == "draft"
        db.rollback()


def test_preflight_fails_closed_without_assignment_or_publication():
    with factories.session() as db:
        _, territory, actor = _draft(db)
        report = inspect_territory_activation_preflight(db, territory.id)
        assert "UNPUBLISHED" in report.issues
        assert "NO_ELIGIBLE_STORE_ASSIGNMENTS" in report.issues
        _publish(db, territory, actor)
        report = inspect_territory_activation_preflight(db, territory.id)
        assert "UNPUBLISHED" not in report.issues
        assert "NO_ELIGIBLE_STORE_ASSIGNMENTS" in report.issues
        db.rollback()


def test_preflight_detects_unpublished_edit_and_inactive_region():
    with factories.session() as db:
        region, territory, actor = _draft(db)
        _publish(db, territory, actor)
        store = factories.make_store(db, is_active=True)
        db.add(StoreDeliveryTerritory(
            store_id=store.id, territory_id=territory.id,
            status="active", delivery_enabled=True,
        ))
        territory.radius_km = 2
        region.status = "inactive"
        db.flush()
        report = inspect_territory_activation_preflight(db, territory.id)
        assert "UNPUBLISHED_GEOMETRY_CHANGES" in report.issues
        assert "REGION_NOT_ACTIVE" in report.issues
        assert report.technical_checks_passed is False
        db.rollback()


def test_preflight_rejects_stale_history_and_disabled_assignment():
    with factories.session() as db:
        _, territory, actor = _draft(db)
        _publish(db, territory, actor)
        store = factories.make_store(db, is_active=True)
        db.add(StoreDeliveryTerritory(
            store_id=store.id, territory_id=territory.id,
            status="active", delivery_enabled=False,
        ))
        territory.published_version = 99
        db.flush()
        report = inspect_territory_activation_preflight(db, territory.id)
        assert "INVALID_PUBLICATION_HISTORY" in report.issues
        assert "NO_ELIGIBLE_STORE_ASSIGNMENTS" in report.issues
        db.rollback()



def test_preflight_excludes_inactive_store_even_with_active_assignment():
    with factories.session() as db:
        _, territory, actor = _draft(db)
        _publish(db, territory, actor)
        store = factories.make_store(db)  # Factory defaults to inactive.
        db.add(StoreDeliveryTerritory(
            store_id=store.id, territory_id=territory.id,
            status="active", delivery_enabled=True,
        ))
        db.flush()
        report = inspect_territory_activation_preflight(db, territory.id)
        assert report.total_assignments == 1
        assert report.eligible_assignments == 0
        assert "NO_ELIGIBLE_STORE_ASSIGNMENTS" in report.issues
        db.rollback()

def test_preflight_missing_territory_and_naive_time():
    with factories.session() as db:
        assert inspect_territory_activation_preflight(db, uuid4()) is None
        from datetime import datetime
        with pytest.raises(ValueError, match="timezone-aware"):
            inspect_territory_activation_preflight(
                db, uuid4(), evaluated_at=datetime(2026, 11, 2),
            )


@pytest.fixture
def users():
    with SessionLocal() as db:
        admin = factories.make_user(db, role=UserRole.ADMIN)
        customer = factories.make_user(db, role=UserRole.CUSTOMER)
        db.commit()
        return str(admin.id), str(customer.id)


def _get(territory_id, user_id=None):
    headers = (
        {"Authorization": f"Bearer {create_access_token(user_id)}"}
        if user_id else {}
    )
    return client.get(
        f"/api/v1/admin/delivery-territories/{territory_id}/activation-preflight",
        headers=headers,
    )


def test_preflight_route_feature_flag_and_authorization(monkeypatch, users):
    admin_id, customer_id = users
    territory_id = uuid4()
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PREVIEW_ENABLED", False)
    assert _get(territory_id, admin_id).status_code == 404
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PREVIEW_ENABLED", True)
    assert _get(territory_id).status_code == 401
    assert _get(territory_id, customer_id).status_code == 403
    assert _get(territory_id, admin_id).status_code == 404


def test_preflight_route_does_not_expose_coordinates_or_grant_activation(monkeypatch, users):
    admin_id, _ = users
    territory_id = uuid4()
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PREVIEW_ENABLED", True)
    monkeypatch.setattr(
        admin_territory_preview, "inspect_territory_activation_preflight",
        lambda db, tid: TerritoryActivationPreflight(
            territory_id=tid, published_version=3,
            total_assignments=2, eligible_assignments=1,
            issues=(), technical_checks_passed=True,
        ),
    )
    response = _get(territory_id, admin_id)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "territory_id": str(territory_id),
        "published_version": 3,
        "total_assignments": 2,
        "eligible_assignments": 1,
        "issues": [],
        "technical_checks_passed": True,
        "activation_authorized": False,
        "checkout_authoritative": False,
    }
    assert "latitude" not in response.text
    assert "longitude" not in response.text
