from fastapi.testclient import TestClient

from app.api.v1.routes import geography
from app.main import app

client = TestClient(app)


def test_location_autocomplete_is_public_and_uses_q(monkeypatch):
    monkeypatch.setattr(geography.rate_limiter, "enforce", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        geography,
        "autocomplete",
        lambda q, latitude=None, longitude=None, session_token=None: [
            {"place_id": "place-1", "text": f"{q}, Pune, Maharashtra", "structured_format": None}
        ],
    )

    response = client.get(
        "/api/v1/location/autocomplete",
        params={"q": "Kothrud", "session_token": "session-12345678"},
    )

    assert response.status_code == 200, response.text
    assert response.json()[0]["place_id"] == "place-1"
    assert response.json()[0]["text"].startswith("Kothrud")


def test_location_place_is_public_and_returns_coordinates(monkeypatch):
    monkeypatch.setattr(geography.rate_limiter, "enforce", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        geography,
        "place_details",
        lambda place_id, session_token=None: {
            "place_id": place_id,
            "formatted_address": "Kothrud, Pune, Maharashtra, India",
            "address_components": [],
            "latitude": 18.5074,
            "longitude": 73.8077,
            "plus_code": None,
        },
    )

    response = client.get(
        "/api/v1/location/place/place-1",
        params={"session_token": "session-12345678"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["latitude"] == 18.5074
    assert response.json()["longitude"] == 73.8077


def test_short_location_query_is_rejected_without_provider_call(monkeypatch):
    monkeypatch.setattr(geography.rate_limiter, "enforce", lambda *args, **kwargs: None)
    response = client.get("/api/v1/location/autocomplete", params={"q": "P"})
    assert response.status_code == 422
