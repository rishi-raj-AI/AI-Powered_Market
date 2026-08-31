from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def seeded_village() -> dict:
    """The seeded pilot village, by identity rather than listing position."""
    villages = client.get("/api/v1/villages").json()
    for village in villages:
        if village["name"] == "Pilot Village":
            return village
    assert villages, "no villages are seeded"
    return villages[0]


def seeded_store() -> dict:
    """The seeded pilot store, by slug rather than listing position."""
    stores = client.get("/api/v1/stores").json()
    for store in stores:
        if store["slug"] == "patil-kirana-pilot":
            return store
    assert stores, "no stores are seeded"
    return stores[0]

OTP = "123456"


def token() -> str:
    phone = f"+917{int(uuid4().hex[:8], 16) % 1_000_000_000:09d}"
    response = client.post(
        "/api/v1/auth/verify-otp",
        json={"phone": phone, "otp": OTP, "full_name": "Coverage Test"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}


def test_address_pin_must_be_inside_active_service_area() -> None:
    access_token = token()
    villages = client.get("/api/v1/villages").json()
    assert villages

    coverage = client.get(
        "/api/v1/location/serviceability",
        params={"latitude": 28.6139, "longitude": 77.2090},
    )
    assert coverage.status_code == 200, coverage.text
    assert coverage.json()["serviceable"] is False

    outside = client.post(
        "/api/v1/addresses/me",
        headers=auth(access_token),
        json={
            "village_id": seeded_village()["id"],
            "label": "Home",
            "landmark": "Outside pilot area",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "is_default": True,
        },
    )
    assert outside.status_code == 422, outside.text
    assert "outside the active GaonOne service area" in outside.json()["detail"]

    half_coordinate = client.post(
        "/api/v1/addresses/me",
        headers=auth(access_token),
        json={
            "village_id": seeded_village()["id"],
            "label": "Home",
            "landmark": "Incomplete pin",
            "latitude": 20.08,
            "is_default": False,
        },
    )
    assert half_coordinate.status_code == 422, half_coordinate.text
