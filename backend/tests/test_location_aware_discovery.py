from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.v1.routes import discovery
from app.db.session import SessionLocal
from app.main import app
from app.models.commerce import Store

client = TestClient(app)


def _seed_store_id():
    with SessionLocal() as db:
        store = db.scalar(select(Store).where(Store.slug == "patil-kirana-pilot"))
        assert store is not None
        return store.id


def test_discovery_ranks_matching_nearby_store(monkeypatch):
    store_id = _seed_store_id()
    monkeypatch.setattr(discovery, "nearby_store_distances", lambda *args, **kwargs: [(store_id, 1.25)])

    response = client.get(
        "/api/v1/discovery/search",
        params={"q": "Patil", "latitude": 18.52, "longitude": 73.85},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["stores"]
    assert payload["stores"][0]["name"] == "Patil Kirana & Daily Needs"
    assert payload["stores"][0]["distance_km"] == 1.25


def test_discovery_returns_available_product_from_nearby_store(monkeypatch):
    store_id = _seed_store_id()
    monkeypatch.setattr(discovery, "nearby_store_distances", lambda *args, **kwargs: [(store_id, 2.0)])

    response = client.get(
        "/api/v1/discovery/search",
        params={"q": "Rice", "latitude": 18.52, "longitude": 73.85},
    )

    assert response.status_code == 200, response.text
    products = response.json()["products"]
    assert products
    assert products[0]["name"] == "Rice"
    assert products[0]["store_name"] == "Patil Kirana & Daily Needs"


def test_discovery_is_empty_when_no_store_is_inside_radius(monkeypatch):
    monkeypatch.setattr(discovery, "nearby_store_distances", lambda *args, **kwargs: [])
    response = client.get(
        "/api/v1/discovery/search",
        params={"q": "Milk", "latitude": 0, "longitude": 0},
    )
    assert response.status_code == 200
    assert response.json()["stores"] == []
    assert response.json()["products"] == []
