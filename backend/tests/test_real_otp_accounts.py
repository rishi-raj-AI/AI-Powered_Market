from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import runpy
from threading import Barrier
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.phone import normalize_indian_phone
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User
from app.api.v1.routes.auth import _login_verified_phone
from app.services.otp import OTPService
from tests import factories

client = TestClient(app)


def auth(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


def test_phone_normalization_is_canonical_and_rejects_ambiguous_values() -> None:
    assert normalize_indian_phone("98765 43210") == "+919876543210"
    assert normalize_indian_phone("+91-98765-43210") == "+919876543210"
    assert normalize_indian_phone("919876543210") == "+919876543210"
    with pytest.raises(ValueError):
        normalize_indian_phone("12345")
    with pytest.raises(ValueError):
        normalize_indian_phone("+449876543210")


def test_direct_otp_metadata_is_truthful_and_identity_is_canonical() -> None:
    phone = f"9{int(uuid4().hex[:8], 16) % 1_000_000_000:09d}"
    requested = client.post("/api/v1/auth/request-otp", json={"phone": phone})
    assert requested.status_code == 200, requested.text
    payload = requested.json()
    assert payload["expires_in_seconds"] == settings.OTP_TTL_SECONDS
    assert payload["resend_after_seconds"] is None
    assert payload["request_limit"] == settings.OTP_MAX_REQUESTS_PER_WINDOW
    assert payload["request_window_seconds"] == settings.OTP_RATE_WINDOW_SECONDS

    verified = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": settings.DEV_OTP})
    assert verified.status_code == 200, verified.text
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {verified.json()['access_token']}"})
    assert me.json()["phone"] == f"+91{phone}"
    with SessionLocal() as db:
        user = db.get(User, me.json()["id"])
        if user:
            db.delete(user)
            db.commit()


def test_returning_identity_preserves_name_disabled_is_rejected_and_profile_is_whitelisted() -> None:
    with SessionLocal() as db:
        existing = factories.make_user(db)
        existing.full_name = "Existing Name"
        db.commit()
        user_id, phone = existing.id, existing.phone
    login = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": settings.DEV_OTP, "full_name": "Replacement"})
    assert login.status_code == 200
    assert client.get("/api/v1/users/me", headers=auth(user_id)).json()["full_name"] == "Existing Name"
    updated = client.patch("/api/v1/users/me", headers=auth(user_id), json={"full_name": "  Asha   Patil  "})
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Asha Patil"
    assert client.patch("/api/v1/users/me", headers=auth(user_id), json={"full_name": "Asha", "role": "admin"}).status_code == 422
    with SessionLocal() as db:
        user = db.get(User, user_id)
        user.is_active = False
        db.commit()
    assert client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": settings.DEV_OTP}).status_code == 403


def test_msg91_direct_provider_is_mocked_and_fails_closed(monkeypatch) -> None:
    service = OTPService()
    monkeypatch.setattr(settings, "APP_ENV", "staging")
    monkeypatch.setattr(settings, "SMS_PROVIDER", "msg91")
    monkeypatch.setattr(settings, "MSG91_AUTH_KEY", "redacted-test-key")
    monkeypatch.setattr(settings, "MSG91_TEMPLATE_ID", "template-test")
    monkeypatch.setattr(service, "_check_send_rate", lambda _: None)
    monkeypatch.setattr(service, "_check_verify_rate", lambda _: True)
    seen = {}

    class Response:
        def __init__(self,status_code=200,payload=None):self.status_code=status_code;self.payload={"type":"success"} if payload is None else payload
        def json(self): return self.payload

    def post(url, **kwargs):
        seen.update({"params":kwargs["params"],"headers":kwargs["headers"]})
        return Response()

    monkeypatch.setattr(httpx, "post", post)
    assert service.issue("+919876543210").expires_in_seconds is None
    assert seen["params"]["mobile"] == "919876543210"
    assert "authkey" not in seen["params"]
    assert seen["headers"]["authkey"] == "redacted-test-key"
    monkeypatch.setattr(httpx,"post",lambda *args,**kwargs:Response(payload=[]))
    with pytest.raises(RuntimeError,match="rejected"):service.issue("+919876543210")

    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", unavailable)
    with pytest.raises(RuntimeError, match="unavailable"):
        service.verify("+919876543210", "123456")


@pytest.mark.parametrize("status,payload",[(200,None),(200,[]),(302,{"type":"success"}),(401,{"type":"error"})])
def test_msg91_nonobject_redirect_and_auth_failures_are_not_authentication(monkeypatch,status,payload) -> None:
    service=OTPService();monkeypatch.setattr(settings,"APP_ENV","staging");monkeypatch.setattr(settings,"SMS_PROVIDER","msg91");monkeypatch.setattr(service,"_check_verify_rate",lambda _:True)
    class Response:
        status_code=status
        def json(self):return payload
    monkeypatch.setattr(httpx,"get",lambda *args,**kwargs:Response())
    with pytest.raises(RuntimeError):service.verify("+919876543210","123456")


def test_msg91_documented_wrong_otp_response_remains_invalid_not_provider_outage(monkeypatch) -> None:
    service=OTPService();monkeypatch.setattr(settings,"APP_ENV","staging");monkeypatch.setattr(settings,"SMS_PROVIDER","msg91");monkeypatch.setattr(service,"_check_verify_rate",lambda _:True)
    class Response:
        status_code=200
        def json(self):return {"type":"error","message":"OTP not match"}
    monkeypatch.setattr(httpx,"get",lambda *args,**kwargs:Response())
    assert service.verify("+919876543210","000000") is False


def test_concurrent_first_login_returns_one_canonical_user() -> None:
    phone=f"+919{int(uuid4().hex[:8],16)%1_000_000_000:09d}";barrier=Barrier(2)
    def login(_):
        with SessionLocal() as db:
            original=db.scalar
            def synchronized(statement,*args,**kwargs):
                result=original(statement,*args,**kwargs)
                if result is None:barrier.wait(timeout=5)
                return result
            db.scalar=synchronized
            return _login_verified_phone(phone,"Concurrent Customer",db).access_token
    with ThreadPoolExecutor(max_workers=2) as pool:tokens=list(pool.map(login,range(2)))
    assert len(tokens)==2
    with SessionLocal() as db:
        users=db.query(User).filter(User.phone==phone).all();assert len(users)==1;db.delete(users[0]);db.commit()


def test_phone_migration_rejects_invalid_and_colliding_rows_before_updates() -> None:
    migration=runpy.run_path(str(Path("alembic/versions/0021_normalize_user_phones.py")))
    plan=migration["_phone_updates"]
    assert plan([{"id":"a","phone":"9876543210"}])==[("a","+919876543210")]
    with pytest.raises(RuntimeError,match="non-canonicalizable"):plan([{"id":"a","phone":"invalid"}])
    with pytest.raises(RuntimeError,match="collide"):plan([{"id":"a","phone":"9876543210"},{"id":"b","phone":"+919876543210"}])
