"""Firebase ID-token boundary for the authentication route.

The rest of the application receives a GaonOne session and never needs to
trust Firebase client state directly. Tests replace ``firebase_token_verifier``
with a deterministic fake; no test contacts Firebase.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass

from app.core.config import settings


class FirebaseTokenInvalid(ValueError):
    pass


class FirebaseVerifierUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class VerifiedFirebaseIdentity:
    subject: str
    display_name: str | None = None


class FirebaseTokenVerifier:
    def verify(self, id_token: str) -> VerifiedFirebaseIdentity:
        if not settings.FIREBASE_PROJECT_ID or not settings.FIREBASE_SERVICE_ACCOUNT_JSON_B64:
            raise FirebaseVerifierUnavailable("Firebase authentication is not configured")
        try:
            import firebase_admin
            from firebase_admin import auth, credentials

            if not firebase_admin._apps:
                info = json.loads(base64.b64decode(settings.FIREBASE_SERVICE_ACCOUNT_JSON_B64).decode("utf-8"))
                firebase_admin.initialize_app(credentials.Certificate(info), {"projectId": settings.FIREBASE_PROJECT_ID})
            claims = auth.verify_id_token(id_token, check_revoked=True)
        except (ValueError, TypeError, json.JSONDecodeError, base64.binascii.Error) as exc:
            raise FirebaseVerifierUnavailable("Firebase authentication is misconfigured") from exc
        except Exception as exc:  # Firebase exceptions vary across SDK versions.
            name = type(exc).__name__
            if name in {"InvalidIdTokenError", "ExpiredIdTokenError", "RevokedIdTokenError", "UserDisabledError"}:
                raise FirebaseTokenInvalid("Firebase token is invalid or expired") from exc
            raise FirebaseVerifierUnavailable("Firebase token verification is unavailable") from exc

        if not isinstance(claims, dict):
            raise FirebaseTokenInvalid("Firebase token verification returned an invalid identity")
        subject = claims.get("uid") or claims.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise FirebaseTokenInvalid("Firebase token did not contain a subject")
        name = claims.get("name")
        return VerifiedFirebaseIdentity(subject=subject.strip(), display_name=name.strip() if isinstance(name, str) and name.strip() else None)


firebase_token_verifier = FirebaseTokenVerifier()
