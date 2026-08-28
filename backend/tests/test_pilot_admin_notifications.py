from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app);OTP="123456"
def token(phone,name=None):
    payload={"phone":phone,"otp":OTP}
    if name:payload["full_name"]=name
    r=client.post("/api/v1/auth/verify-otp",json=payload);assert r.status_code==200,r.text;return r.json()["access_token"]
def auth(t):return {"Authorization":f"Bearer {t}"}
def test_admin_can_activate_delivery_partner_and_notification_flush_is_safe():
    admin=token("+919000000001")
    phone=f"+916{int(uuid4().hex[:9],16)%1_000_000_000:09d}"
    customer=token(phone,"Pilot Rider Candidate")
    me=client.get("/api/v1/users/me",headers=auth(customer));assert me.status_code==200
    user_id=me.json()["id"]
    users=client.get("/api/v1/admin/users",headers=auth(admin));assert users.status_code==200
    assert any(u["id"]==user_id for u in users.json())
    promoted=client.patch(f"/api/v1/admin/users/{user_id}/role",headers=auth(admin),json={"role":"delivery","is_active":True});assert promoted.status_code==200,promoted.text;assert promoted.json()["role"]=="delivery"
    tasks=client.get("/api/v1/delivery/tasks/available",headers=auth(customer));assert tasks.status_code==200,tasks.text
    flushed=client.post("/api/v1/notifications/flush",headers=auth(admin));assert flushed.status_code==200,flushed.text;assert "events" in flushed.json();assert "pushes" in flushed.json()
