from fastapi.testclient import TestClient

from app.api.v1.routes import commerce, geography, store_discovery
from app.main import app

client = TestClient(app)


def test_nearby_store_route_prefers_indexed_postgis_handler(monkeypatch) -> None:
    monkeypatch.setattr(store_discovery, "nearby_store_distances", lambda *args, **kwargs: [])

    def legacy_distance_must_not_run(*args, **kwargs):
        raise AssertionError("legacy Haversine nearby-store handler was selected")

    monkeypatch.setattr(commerce, "_distance_km", legacy_distance_must_not_run)
    response = client.get(
        "/api/v1/stores/nearby",
        params={"lat": 18.5204, "lng": 73.8567, "radius_km": 15, "delivery": True},
    )
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_serviceability_route_uses_postgis_service(monkeypatch) -> None:
    monkeypatch.setattr(geography, "serviceability_for_point", lambda *args, **kwargs: None)
    response = client.get(
        "/api/v1/location/serviceability",
        params={"latitude": 18.5204, "longitude": 73.8567},
    )
    assert response.status_code == 200, response.text
    assert response.json()["serviceable"] is False
