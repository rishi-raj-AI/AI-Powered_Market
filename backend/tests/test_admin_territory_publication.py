"""HTTP permission and disabled-flag tests for initial draft publication."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes import admin_territory_publication
from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.user import UserRole
from app.services.territory_publication import PublicationRejected, PublicationResult
from tests import factories

client = TestClient(app)


@pytest.fixture
def users():
    with SessionLocal() as db:
        customer = factories.make_user(db, role=UserRole.CUSTOMER)
        admin = factories.make_user(db, role=UserRole.ADMIN)
        super_admin = factories.make_user(db, role=UserRole.ADMIN)
        super_admin.is_super_admin = True
        db.commit()
        return str(customer.id), str(admin.id), str(super_admin.id)


def _headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _post(territory_id, *, user_id=None, reason="Approved synthetic territory publication"):
    return client.post(
        f"/api/v1/admin/delivery-territories/{territory_id}/publish-initial-draft",
        json={"expected_published_version": None, "change_reason": reason},
        headers=_headers(user_id) if user_id else {},
    )


def test_publication_disabled_even_for_super_admin(monkeypatch, users):
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PUBLISH_ENABLED", False)
    response = _post(uuid4(), user_id=users[2])
    assert response.status_code == 404


def test_publication_denies_anonymous_customer_and_regular_admin(monkeypatch, users):
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PUBLISH_ENABLED", True)
    territory_id = uuid4()
    assert _post(territory_id).status_code == 401
    assert _post(territory_id, user_id=users[0]).status_code == 403
    assert _post(territory_id, user_id=users[1]).status_code == 403


def test_super_admin_receives_non_activation_contract(monkeypatch, users):
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PUBLISH_ENABLED", True)
    territory_id = uuid4()
    called = []

    def fake_publish(db, **kwargs):
        called.append(kwargs)
        return PublicationResult(
            territory_id=territory_id, published_version=1, status="draft",
        )

    monkeypatch.setattr(admin_territory_publication, "publish_initial_draft", fake_publish)
    response = _post(territory_id, user_id=users[2])
    assert response.status_code == 200, response.text
    assert response.json() == {
        "territory_id": str(territory_id),
        "published_version": 1,
        "status": "draft",
        "coverage_activated": False,
        "checkout_authoritative": False,
    }
    assert called[0]["expected_published_version"] is None


def test_invalid_reason_is_rejected_before_mutation(monkeypatch, users):
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PUBLISH_ENABLED", True)
    assert _post(uuid4(), user_id=users[2], reason="short").status_code == 422


def test_version_conflict_returns_409(monkeypatch, users):
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PUBLISH_ENABLED", True)

    def fail_publish(db, **kwargs):
        raise PublicationRejected("version_conflict", "Territory publication version changed")

    monkeypatch.setattr(admin_territory_publication, "publish_initial_draft", fail_publish)
    response = _post(uuid4(), user_id=users[2])
    assert response.status_code == 409
    assert "version changed" in response.json()["detail"]
