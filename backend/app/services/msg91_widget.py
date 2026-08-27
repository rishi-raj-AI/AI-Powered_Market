from __future__ import annotations

from dataclasses import dataclass
import logging

import httpx

from app.core.config import settings

VERIFY_ACCESS_TOKEN_URL = "https://control.msg91.com/api/v5/widget/verifyAccessToken"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VerifiedWidgetIdentity:
    identifier: str
    raw: dict


def _extract_identifier(payload: dict) -> str | None:
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
    digits = value[1:] if value.startswith("+") else value
    if digits.startswith("91") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+91{digits}"
    raise ValueError("MSG91 returned an unsupported mobile identifier")


def _provider_message(payload: dict, fallback: str) -> str:
    for key in ("message", "error", "detail", "msg"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("message", "error", "detail", "msg"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return fallback


def _safe_provider_diagnostic(payload: object) -> object:
    """Keep provider diagnostics useful without ever logging credentials or tokens."""
    if not isinstance(payload, dict):
        return {"response_type": type(payload).__name__}

    safe: dict[str, object] = {}
    for key in ("type", "message", "error", "detail", "msg", "status", "code"):
        value = payload.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[key] = value

    data = payload.get("data")
    if isinstance(data, dict):
        safe_data: dict[str, object] = {}
        for key in ("type", "message", "error", "detail", "msg", "status", "code"):
            value = data.get(key)
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe_data[key] = value
        if safe_data:
            safe["data"] = safe_data

    safe["response_keys"] = sorted(str(key) for key in payload.keys())
    return safe


def verify_widget_access_token(access_token: str) -> VerifiedWidgetIdentity:
    if not settings.MSG91_AUTH_KEY:
        raise RuntimeError("MSG91 server auth key is not configured")

    try:
        response = httpx.post(
            VERIFY_ACCESS_TOKEN_URL,
            json={
                "authkey": settings.MSG91_AUTH_KEY,
                "access-token": access_token,
            },
            headers={"Content-Type": "application/json"},
            timeout=settings.SMS_HTTP_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        logger.warning("MSG91 verifyAccessToken network failure: %s", type(exc).__name__)
        raise RuntimeError("MSG91 verification service is unavailable") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        logger.warning(
            "MSG91 verifyAccessToken invalid JSON: status=%s content_type=%s",
            response.status_code,
            response.headers.get("content-type"),
        )
        raise RuntimeError("MSG91 returned an invalid verification response") from exc

    if response.status_code >= 400:
        logger.warning(
            "MSG91 verifyAccessToken rejected: status=%s diagnostic=%r",
            response.status_code,
            _safe_provider_diagnostic(payload),
        )

    if response.status_code >= 500:
        raise RuntimeError(_provider_message(payload, "MSG91 verification service is unavailable"))
    if response.status_code >= 400:
        raise ValueError(_provider_message(payload, "MSG91 access token is invalid or expired"))

    identifier = _extract_identifier(payload)
    if identifier is None:
        logger.warning(
            "MSG91 verifyAccessToken missing identifier: status=%s diagnostic=%r",
            response.status_code,
            _safe_provider_diagnostic(payload),
        )
        raise ValueError(_provider_message(payload, "MSG91 verification response did not contain a verified identifier"))

    return VerifiedWidgetIdentity(identifier=_normalize_indian_phone(identifier), raw=payload)
