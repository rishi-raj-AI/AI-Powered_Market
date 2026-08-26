from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

import redis
from redis.exceptions import RedisError

from app.core.config import settings


@dataclass(frozen=True)
class OTPResult:
    message: str
    dev_otp: str | None = None


class OTPService:
    """OTP issuance/verification with Redis-backed TTL and abuse controls.

    Development keeps a deterministic OTP so automated tests and local demos stay
    frictionless. Production requires a real SMS provider and never returns the OTP.
    """

    def __init__(self) -> None:
        self._redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

    @staticmethod
    def _phone_hash(phone: str) -> str:
        return hashlib.sha256(phone.encode("utf-8")).hexdigest()

    def _otp_key(self, phone: str) -> str:
        return f"auth:otp:{self._phone_hash(phone)}"

    def _send_key(self, phone: str) -> str:
        return f"auth:otp-send:{self._phone_hash(phone)}"

    def _verify_key(self, phone: str) -> str:
        return f"auth:otp-verify:{self._phone_hash(phone)}"

    def issue(self, phone: str) -> OTPResult:
        otp = settings.DEV_OTP if settings.APP_ENV == "development" else f"{secrets.randbelow(1_000_000):06d}"

        try:
            sends = self._redis.incr(self._send_key(phone))
            if sends == 1:
                self._redis.expire(self._send_key(phone), settings.OTP_RATE_WINDOW_SECONDS)
            if sends > settings.OTP_MAX_REQUESTS_PER_WINDOW:
                raise ValueError("Too many OTP requests. Please try again later.")
            self._redis.setex(self._otp_key(phone), settings.OTP_TTL_SECONDS, otp)
        except RedisError:
            # Local development must remain usable even if Redis is temporarily down.
            if settings.APP_ENV != "development":
                raise RuntimeError("OTP storage is unavailable")

        if settings.APP_ENV == "development":
            return OTPResult(message="Development OTP generated", dev_otp=otp)

        if settings.SMS_PROVIDER == "none":
            raise RuntimeError("SMS OTP provider is not configured")

        # Provider adapters are intentionally configured behind this boundary.
        # The concrete MSG91/Twilio call is enabled once production credentials exist.
        raise RuntimeError(f"SMS provider '{settings.SMS_PROVIDER}' is not configured")

    def verify(self, phone: str, supplied_otp: str) -> bool:
        if settings.APP_ENV == "development" and supplied_otp == settings.DEV_OTP:
            return True

        try:
            attempts = self._redis.incr(self._verify_key(phone))
            if attempts == 1:
                self._redis.expire(self._verify_key(phone), settings.OTP_TTL_SECONDS)
            if attempts > settings.OTP_MAX_VERIFY_ATTEMPTS:
                return False
            expected = self._redis.get(self._otp_key(phone))
            if expected and secrets.compare_digest(expected, supplied_otp):
                self._redis.delete(self._otp_key(phone), self._verify_key(phone))
                return True
            return False
        except RedisError:
            return False


otp_service = OTPService()
