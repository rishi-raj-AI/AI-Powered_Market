from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
OTP = "123456"


def token(phone: str) -> str:
    response = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": OTP})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}


def test_multilingual_order_intent_and_catalog_permissions() -> None:
    customer = token("+919100000001")
    marathi = client.post(
        "/api/v1/ai/order-intent",
        headers=auth(customer),
        json={"text": "मला 2 किलो कांदा हवा", "input_mode": "voice_transcript"},
    )
    assert marathi.status_code == 200, marathi.text
    payload = marathi.json()
    assert payload["language"] == "mr"
    assert payload["input_mode"] == "voice_transcript"
    assert payload["items"][0]["query"] == "onion"
    assert payload["items"][0]["quantity"] == 2
    assert payload["items"][0]["unit"] == "kg"
    assert payload["requires_confirmation"] is False

    forbidden = client.post(
        "/api/v1/ai/catalog-assist",
        headers=auth(customer),
        json={"name": "Premium rice 5 kg"},
    )
    assert forbidden.status_code == 403, forbidden.text

    merchant = token("+919000000003")
    catalog = client.post(
        "/api/v1/ai/catalog-assist",
        headers=auth(merchant),
        json={"name": "Premium rice 5 kg", "description": "daily grocery rice"},
    )
    assert catalog.status_code == 200, catalog.text
    draft = catalog.json()
    assert draft["category_hint"] == "grocery"
    assert draft["unit_hint"] == "kg"
    assert "rice" in draft["search_keywords"]
    assert draft["requires_merchant_review"] is True
