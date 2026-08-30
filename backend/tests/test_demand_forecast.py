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


def test_merchant_demand_forecast_contract_and_rbac() -> None:
    merchant = token("+919000000003")
    stores = client.get("/api/v1/stores/mine", headers=auth(merchant))
    assert stores.status_code == 200, stores.text
    assert stores.json()
    store_id = stores.json()[0]["id"]

    forecast = client.get(
        f"/api/v1/merchant/stores/{store_id}/demand-forecast",
        headers=auth(merchant),
        params={"window_days": 28, "horizon_days": 7},
    )
    assert forecast.status_code == 200, forecast.text
    payload = forecast.json()
    assert payload["store_id"] == store_id
    assert payload["method"] == "weighted_recent_sales_velocity_v1"
    assert payload["window_days"] == 28
    assert payload["horizon_days"] == 7
    assert isinstance(payload["products"], list)
    if payload["products"]:
        item = payload["products"][0]
        assert item["forecast_units"] >= 0
        assert item["recommended_reorder_units"] >= 0
        assert item["confidence"] in {"low", "medium", "high"}
        assert item["recommendation"] in {"reorder", "hold", "maintain"}
        assert item["reason"]

    customer = token("+919100000002")
    forbidden = client.get(
        f"/api/v1/merchant/stores/{store_id}/demand-forecast",
        headers=auth(customer),
    )
    assert forbidden.status_code == 403, forbidden.text
