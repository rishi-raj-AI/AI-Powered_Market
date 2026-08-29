from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

import httpx
import redis
from redis.exceptions import RedisError

from app.core.config import settings


@dataclass(frozen=True)
class OTPResult:
    message: str
    dev_otp: str | None = None


class OTPService:
    """OTP issuance/verification with Redis-backed abuse controls."""

    def __init__(self) -> None:
        self._redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

    @staticmethod
    def _phone_hash(phone: str) -> str:
        return hashlib.sha256(phone.encode("utf-8")).hexdigest()

    @staticmethod
    def _msg91_mobile(phone: str) -> str:
        return phone.lstrip("+")

    def _otp_key(self, phone: str) -> str:
        return f"auth:otp:{self._phone_hash(phone)}"

    def _send_key(self, phone: str) -> str:
        return f"auth:otp-send:{self._phone_hash(phone)}"

    def _verify_key(self, phone: str) -> str:
        return f"auth:otp-verify:{self._phone_hash(phone)}"

    def _check_send_rate(self, phone: str) -> None:
        try:
            sends = self._redis.incr(self._send_key(phone))
            if sends == 1:
                self._redis.expire(self._send_key(phone), settings.OTP_RATE_WINDOW_SECONDS)
            if sends > settings.OTP_MAX_REQUESTS_PER_WINDOW:
                raise ValueError("Too many OTP requests. Please try again later.")
        except RedisError as exc:
            if settings.APP_ENV != "development":
                raise RuntimeError("OTP rate-limit storage is unavailable") from exc

    def _check_verify_rate(self, phone: str) -> bool:
        try:
            attempts = self._redis.incr(self._verify_key(phone))
            if attempts == 1:
                self._redis.expire(self._verify_key(phone), settings.OTP_TTL_SECONDS)
            return attempts <= settings.OTP_MAX_VERIFY_ATTEMPTS
        except RedisError:
            return settings.APP_ENV == "development"

    def _msg91_send(self, phone: str) -> None:
        try:
            response = httpx.post(
                "https://control.msg91.com/api/v5/otp",
                params={
                    "template_id": settings.MSG91_TEMPLATE_ID,
                    "mobile": self._msg91_mobile(phone),
                    "authkey": settings.MSG91_AUTH_KEY,
                },
                headers={"accept": "application/json"},
                timeout=settings.SMS_HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError("OTP provider request failed") from exc

        if str(payload.get("type", "")).lower() != "success":
            raise RuntimeError("OTP provider rejected the request")

    def _msg91_verify(self, phone: str, otp: str) -> bool:
        try:
            response = httpx.get(
                "https://control.msg91.com/api/v5/otp/verify",
                params={"otp": otp, "mobile": self._msg91_mobile(phone)},
                headers={"authkey": settings.MSG91_AUTH_KEY or "", "accept": "application/json"},
                timeout=settings.SMS_HTTP_TIMEOUT_SECONDS,
            )
            if response.status_code != 200:
                return False
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return False

        return str(payload.get("type", "")).lower() == "success"

    def issue(self, phone: str) -> OTPResult:
        self._check_send_rate(phone)

        if settings.APP_ENV == "development":
            otp = settings.DEV_OTP or f"{secrets.randbelow(1_000_000):06d}"
            try:
                self._redis.setex(self._otp_key(phone), settings.OTP_TTL_SECONDS, otp)
            except RedisError:
                pass
            return OTPResult(message="Development OTP generated", dev_otp=otp)

        if settings.SMS_PROVIDER == "msg91":
            self._msg91_send(phone)
            return OTPResult(message="OTP sent")

        raise RuntimeError("SMS OTP provider is not configured")

    def verify(self, phone: str, supplied_otp: str) -> bool:
        if not self._check_verify_rate(phone):
            return False

        if settings.APP_ENV == "development":
            if supplied_otp == settings.DEV_OTP:
                try:
                    self._redis.delete(self._otp_key(phone), self._verify_key(phone))
                except RedisError:
                    pass
                return True
            try:
                expected = self._redis.get(self._otp_key(phone))
                if expected and secrets.compare_digest(expected, supplied_otp):
                    self._redis.delete(self._otp_key(phone), self._verify_key(phone))
                    return True
            except RedisError:
                pass
            return False

        if settings.SMS_PROVIDER == "msg91":
            verified = self._msg91_verify(phone, supplied_otp)
            if verified:
                try:
                    self._redis.delete(self._verify_key(phone))
                except RedisError:
                    pass
            return verified

        return False


otp_service = OTPService()
