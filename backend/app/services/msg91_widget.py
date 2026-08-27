from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import settings

VERIFY_ACCESS_TOKEN_URL = "https://control.msg91.com/api/v5/widget/verifyAccessToken"


@dataclass(frozen=True)
class VerifiedWidgetIdentity:
    identifier: str
    raw: dict


def _extract_identifier(payload: dict) -> str | None:
    """Extract the verified identifier across MSG91 response variants."""
    candidates = [
        payload.get("identifier"),
        payload.get("mobile"),
        payload.get("phone"),
        payload.get("mobile_number"),
    ]
    data = payload.get("data")
    if isinstance(data, dict):
        candidates.extend(
            [
                data.get("identifier"),
                data.get("mobile"),
                data.get("phone"),
                data.get("mobile_number"),
            ]
        )
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalize_indian_phone(identifier: str) -> str:
    value = identifier.strip().replace(" ", "").replace("-", "")
    if value.startswith("+"):
        digits = value[1:]
    else:
        digits = value
    if digits.startswith("91") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+91{digits}"
    raise ValueError("MSG91 returned an unsupported mobile identifier")


def verify_widget_access_token(access_token: str) -> VerifiedWidgetIdentity:
    if not settings.MSG91_WIDGET_AUTH_KEY:
        raise RuntimeError("MSG91 widget server auth key is not configured")

    try:
        response = httpx.post(
            VERIFY_ACCESS_TOKEN_URL,
            json={
                "authkey": settings.MSG91_WIDGET_AUTH_KEY,
                "access-token": access_token,
            },
            headers={"Content-Type": "application/json"},
            timeout=settings.SMS_HTTP_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise RuntimeError("MSG91 verification service is unavailable") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("MSG91 returned an invalid verification response") from exc

    if response.status_code >= 500:
        raise RuntimeError("MSG91 verification service is unavailable")
    if response.status_code >= 400:
        raise ValueError("MSG91 access token is invalid or expired")

    identifier = _extract_identifier(payload)
    if identifier is None:
        raise ValueError("MSG91 verification response did not contain a verified identifier")

    return VerifiedWidgetIdentity(identifier=_normalize_indian_phone(identifier), raw=payload)
