from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
OTP = "123456"


def token(phone: str, name: str | None = None) -> str:
    payload = {"phone": phone, "otp": OTP}
    if name:
        payload["full_name"] = name
    response = client.post("/api/v1/auth/verify-otp", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}


def phone(prefix: int) -> str:
    return f"+91{prefix}{int(uuid4().hex[:8], 16) % 1_000_000_000:09d}"


def _ready_order(customer_token: str, merchant_token: str, address_id: str, listing_id: str) -> str:
    add = client.post("/api/v1/cart/items",headers=auth(customer_token),json={"store_product_id":listing_id,"quantity":1})
    assert add.status_code == 200, add.text
    checkout = client.post("/api/v1/orders/checkout",headers=auth(customer_token),json={"address_id":address_id,"payment_method":"cod"})
    assert checkout.status_code == 201, checkout.text
    order_id = checkout.json()["id"]
    for state in ["accepted","preparing","ready"]:
        response = client.patch(f"/api/v1/merchant/orders/{order_id}/status",headers=auth(merchant_token),json={"status":state})
        assert response.status_code == 200, response.text
    return order_id


def test_admin_can_assign_recover_and_reassign_ready_delivery() -> None:
    admin_token=token("+919000000001");merchant_token=token("+919000000003");customer_token=token(phone(7),"Dispatch Customer");rider_token=token(phone(6),"Dispatch Rider")
    rider=client.get("/api/v1/users/me",headers=auth(rider_token)).json()
    promote=client.patch(f"/api/v1/admin/users/{rider['id']}/role",headers=auth(admin_token),json={"role":"delivery","is_active":True})
    assert promote.status_code==200,promote.text
    store=client.get("/api/v1/stores").json()[0];listing_id=client.get(f"/api/v1/stores/{store['id']}/products").json()[0]["id"];village_id=client.get("/api/v1/villages").json()[0]["id"]
    address=client.post("/api/v1/addresses/me",headers=auth(customer_token),json={"village_id":village_id,"label":"Home","landmark":"Dispatch Chowk","latitude":18.5208,"longitude":73.8572,"is_default":True})
    assert address.status_code==201,address.text
    address_id=address.json()["id"]

    first_order=_ready_order(customer_token,merchant_token,address_id,listing_id)
    first_task=next(item for item in client.get("/api/v1/delivery/tasks/available",headers=auth(admin_token)).json() if item["order_id"]==first_order)
    assigned=client.post(f"/api/v1/admin/deliveries/{first_task['id']}/assign",headers=auth(admin_token),json={"rider_id":rider["id"]})
    assert assigned.status_code==200,assigned.text
    assert assigned.json()["delivery_partner_id"]==rider["id"]
    assert assigned.json()["status"]=="assigned"

    active=client.get("/api/v1/admin/deliveries/active",headers=auth(admin_token))
    assert active.status_code==200,active.text
    assert any(item["id"]==first_task["id"] and item["rider_phone"]==rider["phone"] for item in active.json())

    second_order=_ready_order(customer_token,merchant_token,address_id,listing_id)
    second_task=next(item for item in client.get("/api/v1/delivery/tasks/available",headers=auth(admin_token)).json() if item["order_id"]==second_order)
    rider_available=client.get("/api/v1/delivery/tasks/available",headers=auth(rider_token))
    assert rider_available.status_code==200,rider_available.text
    assert rider_available.json()==[]
    overloaded=client.post(f"/api/v1/admin/deliveries/{second_task['id']}/assign",headers=auth(admin_token),json={"rider_id":rider["id"]})
    assert overloaded.status_code==409,overloaded.text
    assert overloaded.json()["detail"]=="Rider already has an active delivery"

    released=client.post(f"/api/v1/admin/deliveries/{first_task['id']}/unassign",headers=auth(admin_token))
    assert released.status_code==200,released.text
    assert released.json()["status"]=="unassigned"
    assert released.json()["delivery_partner_id"] is None

    reassigned=client.post(f"/api/v1/admin/deliveries/{second_task['id']}/assign",headers=auth(admin_token),json={"rider_id":rider["id"]})
    assert reassigned.status_code==200,reassigned.text
    assert reassigned.json()["delivery_partner_id"]==rider["id"]

    picked_up=client.patch(f"/api/v1/delivery/{second_task['id']}/status",headers=auth(rider_token),json={"status":"picked_up"})
    assert picked_up.status_code==200,picked_up.text
    locked=client.post(f"/api/v1/admin/deliveries/{second_task['id']}/unassign",headers=auth(admin_token))
    assert locked.status_code==409,locked.text
    assert "awaiting pickup" in locked.json()["detail"]
