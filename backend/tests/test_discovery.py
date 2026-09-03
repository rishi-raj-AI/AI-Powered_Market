from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.v1.routes import discovery
from app.db.session import SessionLocal
from app.main import app
from tests import factories

client = TestClient(app)


def _catalogue():
    with SessionLocal() as db:
        store = factories.make_store(db, is_active=True)
        store.name = "Patil Daily Needs"
        store.landmark = "Niphad bus stand"
        listing = factories.make_listing(db, store, price=Decimal("72.50"), stock=8)
        listing.product.name = "Kolam Rice"
        listing.product.brand = "Gaon Fresh"
        db.commit()
        return store.id, listing.id


def test_discovery_search_ranks_nearby_available_inventory(monkeypatch):
    store_id, listing_id = _catalogue()
    monkeypatch.setattr(
        discovery, "nearby_store_distances", lambda *args, **kwargs: [(store_id, 1.25)]
    )

    response = client.get(
        "/api/v1/discovery/search",
        params={"q": "Rice", "latitude": 20.08, "longitude": 74.11, "delivery": True},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["products"][0]["listing_id"] == str(listing_id)
    assert result["products"][0]["name"] == "Kolam Rice"
    assert result["products"][0]["distance_km"] == 1.25


def test_discovery_passes_delivery_filter_to_postgis(monkeypatch):
    calls = []

    def nearby(*args):
        calls.append(args)
        return []

    monkeypatch.setattr(discovery, "nearby_store_distances", nearby)
    response = client.get(
        "/api/v1/discovery/search",
        params={
            "q": "Rice",
            "latitude": 20.08,
            "longitude": 74.11,
            "delivery": True,
        },
    )
    assert response.status_code == 200
    assert calls[0][-1] is True


def test_discovery_excludes_unavailable_and_out_of_stock_products(monkeypatch):
    store_id, _ = _catalogue()
    monkeypatch.setattr(
        discovery, "nearby_store_distances", lambda *args, **kwargs: [(store_id, 2.0)]
    )
    with SessionLocal() as db:
        store = db.get(discovery.Store, store_id)
        unavailable = factories.make_listing(db, store, stock=0)
        unavailable.product.name = "Rice Flour"
        db.commit()

    response = client.get(
        "/api/v1/discovery/search",
        params={"q": "Rice", "latitude": 20.08, "longitude": 74.11},
    )
    assert response.status_code == 200
    assert [item["name"] for item in response.json()["products"]] == ["Kolam Rice"]


def test_suggestions_are_deterministic_and_location_aware(monkeypatch):
    store_id, _ = _catalogue()
    monkeypatch.setattr(
        discovery, "nearby_store_distances", lambda *args, **kwargs: [(store_id, 0.75)]
    )

    response = client.get(
        "/api/v1/discovery/suggestions",
        params={"q": "Kol", "latitude": 20.08, "longitude": 74.11},
    )
    assert response.status_code == 200, response.text
    assert response.json()[0]["kind"] == "product"
    assert response.json()[0]["label"] == "Kolam Rice"
    assert response.json()[0]["distance_km"] == 0.75


def test_discovery_returns_empty_when_no_store_is_nearby(monkeypatch):
    monkeypatch.setattr(discovery, "nearby_store_distances", lambda *args, **kwargs: [])
    response = client.get(
        "/api/v1/discovery/search",
        params={"q": "Milk", "latitude": 0, "longitude": 0},
    )
    assert response.status_code == 200
    assert response.json()["stores"] == []
    assert response.json()["products"] == []


def test_text_ranking_prefers_exact_then_prefix_then_contains():
    assert discovery._prefix_rank("Milk", "milk") == 0
    assert discovery._prefix_rank("Milk powder", "milk") == 1
    assert discovery._prefix_rank("Fresh milk", "milk") == 2
    assert discovery._prefix_rank(None, "milk") == 99
