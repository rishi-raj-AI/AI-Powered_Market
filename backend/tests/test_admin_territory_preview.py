"""Access-control and privacy regressions for the opt-in admin preview route.

The spatial predicate itself is exercised against real PostGIS in
test_territory_preview.py. This suite verifies HTTP authorization and the
non-authoritative, coordinate-free response contract.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes import admin_territory_preview
from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.user import UserRole
from app.services.territory_preview import TerritoryMatch
from tests import factories

client = TestClient(app)
PATH = "/api/v1/admin/delivery-territories/preview"


@pytest.fixture
def identities():
    with SessionLocal() as db:
        admin = factories.make_user(db, role=UserRole.ADMIN)
        customer = factories.make_user(db, role=UserRole.CUSTOMER)
        store = factories.make_store(db)
        db.commit()
        return str(admin.id), str(customer.id), str(store.id)


def _headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _payload(store_id):
    return {"store_id": store_id, "latitude": 18.52, "longitude": 73.85}


def test_preview_disabled_by_default(monkeypatch, identities):
    admin_id, _, store_id = identities
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PREVIEW_ENABLED", False)
    response = client.post(PATH, json=_payload(store_id), headers=_headers(admin_id))
    assert response.status_code == 404


def test_preview_rejects_anonymous_and_customer(monkeypatch, identities):
    _, customer_id, store_id = identities
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PREVIEW_ENABLED", True)
    assert client.post(PATH, json=_payload(store_id)).status_code == 401
    assert client.post(
        PATH, json=_payload(store_id), headers=_headers(customer_id),
    ).status_code == 403


def test_preview_has_no_checkout_or_location_claim(monkeypatch, identities):
    admin_id, _, store_id = identities
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PREVIEW_ENABLED", True)
    response = client.post(PATH, json=_payload(store_id), headers=_headers(admin_id))
    assert response.status_code == 200, response.text
    assert response.json() == {
        "geographic_match": False,
        "territory_id": None,
        "assignment_id": None,
        "geometry_type": None,
        "checkout_authoritative": False,
    }


def test_preview_match_never_echoes_coordinates(monkeypatch, identities):
    admin_id, _, store_id = identities
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PREVIEW_ENABLED", True)
    territory_id, assignment_id = uuid4(), uuid4()
    monkeypatch.setattr(
        admin_territory_preview,
        "match_active_store_territory",
        lambda *args, **kwargs: TerritoryMatch(
            territory_id=territory_id,
            assignment_id=assignment_id,
            geometry_type="circle",
            territory_priority=0,
            assignment_priority=0,
        ),
    )
    response = client.post(PATH, json=_payload(store_id), headers=_headers(admin_id))
    assert response.status_code == 200, response.text
    assert response.json() == {
        "geographic_match": True,
        "territory_id": str(territory_id),
        "assignment_id": str(assignment_id),
        "geometry_type": "circle",
        "checkout_authoritative": False,
    }
    assert "latitude" not in response.text
    assert "longitude" not in response.text


@pytest.mark.parametrize(
    "latitude,longitude",
    [(91, 0), (0, -181), ("NaN", 0), ("Infinity", 0)],
)
def test_preview_rejects_invalid_coordinates(monkeypatch, identities, latitude, longitude):
    admin_id, _, store_id = identities
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PREVIEW_ENABLED", True)
    response = client.post(
        PATH,
        json={"store_id": store_id, "latitude": latitude, "longitude": longitude},
        headers=_headers(admin_id),
    )
    assert response.status_code == 422


def test_preview_does_not_disclose_unknown_store(monkeypatch, identities):
    admin_id, _, _ = identities
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PREVIEW_ENABLED", True)
    response = client.post(
        PATH, json=_payload(str(uuid4())), headers=_headers(admin_id),
    )
    assert response.status_code == 404
