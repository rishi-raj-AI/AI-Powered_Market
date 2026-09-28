from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.v1.routes import auth as auth_routes
from app.api.v1.routes.auth import _login_firebase_identity
from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.user import ExternalIdentity, User
from app.services.firebase_auth import FirebaseTokenInvalid, VerifiedFirebaseIdentity

client = TestClient(app)


class FakeVerifier:
    def __init__(self, identity: VerifiedFirebaseIdentity | Exception):
        self.identity = identity

    def verify(self, _: str) -> VerifiedFirebaseIdentity:
        if isinstance(self.identity, Exception):
            raise self.identity
        return self.identity


def _firebase_enabled(monkeypatch, verifier) -> None:
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "firebase")
    monkeypatch.setattr(settings, "SMS_AUTH_ENABLED", False)
    monkeypatch.setattr(auth_routes, "firebase_token_verifier", verifier)


def _delete_subject(subject: str) -> None:
    with SessionLocal() as db:
        identity = db.scalar(select(ExternalIdentity).where(ExternalIdentity.provider == "firebase", ExternalIdentity.subject == subject))
        if identity:
            user = db.get(User, identity.user_id)
            db.delete(identity)
            if user:
                db.delete(user)
            db.commit()


def test_firebase_exchange_creates_one_account_reuses_identity_and_issues_session(monkeypatch) -> None:
    subject = f"firebase-{uuid4()}"
    _firebase_enabled(monkeypatch, FakeVerifier(VerifiedFirebaseIdentity(subject=subject, display_name="Asha Patil")))
    try:
        first = client.post("/api/v1/auth/firebase/exchange", json={"id_token": "x" * 24})
        assert first.status_code == 200, first.text
        token = first.json()["access_token"]
        me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["phone"] is None
        assert me.json()["full_name"] == "Asha Patil"

        repeated = client.post("/api/v1/auth/firebase/exchange", json={"id_token": "y" * 24})
        assert repeated.status_code == 200, repeated.text
        with SessionLocal() as db:
            identities = list(db.scalars(select(ExternalIdentity).where(ExternalIdentity.provider == "firebase", ExternalIdentity.subject == subject)))
            assert len(identities) == 1
    finally:
        _delete_subject(subject)


def test_firebase_exchange_rejects_invalid_malformed_or_missing_subject(monkeypatch) -> None:
    _firebase_enabled(monkeypatch, FakeVerifier(FirebaseTokenInvalid("Firebase token is invalid or expired")))
    invalid = client.post("/api/v1/auth/firebase/exchange", json={"id_token": "x" * 24})
    assert invalid.status_code == 401
    malformed = client.post("/api/v1/auth/firebase/exchange", json={"id_token": "short"})
    assert malformed.status_code == 422
    _firebase_enabled(monkeypatch, FakeVerifier(VerifiedFirebaseIdentity(subject="")))
    missing_subject = client.post("/api/v1/auth/firebase/exchange", json={"id_token": "x" * 24})
    assert missing_subject.status_code == 401


def test_disabled_firebase_account_cannot_receive_a_new_session(monkeypatch) -> None:
    subject = f"firebase-{uuid4()}"
    _firebase_enabled(monkeypatch, FakeVerifier(VerifiedFirebaseIdentity(subject=subject)))
    try:
        assert client.post("/api/v1/auth/firebase/exchange", json={"id_token": "x" * 24}).status_code == 200
        with SessionLocal() as db:
            identity = db.scalar(select(ExternalIdentity).where(ExternalIdentity.subject == subject))
            user = db.get(User, identity.user_id)
            user.is_active = False
            db.commit()
        assert client.post("/api/v1/auth/firebase/exchange", json={"id_token": "x" * 24}).status_code == 403
    finally:
        _delete_subject(subject)


def test_concurrent_first_login_keeps_one_identity_and_one_account() -> None:
    subject = f"firebase-{uuid4()}"
    barrier = Barrier(2)

    def exchange() -> str:
        with SessionLocal() as db:
            barrier.wait()
            return _login_firebase_identity(subject, "Concurrent Asha", db).access_token

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            tokens = list(pool.map(lambda _: exchange(), range(2)))
        assert all(tokens)
        with SessionLocal() as db:
            identities = list(db.scalars(select(ExternalIdentity).where(ExternalIdentity.provider == "firebase", ExternalIdentity.subject == subject)))
            assert len(identities) == 1
            assert db.scalar(select(User).where(User.id == identities[0].user_id)) is not None
    finally:
        _delete_subject(subject)


def test_sms_routes_are_unavailable_when_sms_auth_is_disabled(monkeypatch) -> None:
    _firebase_enabled(monkeypatch, FakeVerifier(FirebaseTokenInvalid("unused")))
    assert client.post("/api/v1/auth/request-otp", json={"phone": "9876543210"}).status_code == 404
    assert client.post("/api/v1/auth/verify-otp", json={"phone": "9876543210", "otp": "123456"}).status_code == 404
