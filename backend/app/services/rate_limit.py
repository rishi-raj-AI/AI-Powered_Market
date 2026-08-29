from __future__ import annotations

import hashlib

import redis
from redis.exceptions import RedisError

from app.core.config import settings


class RateLimitExceeded(ValueError):
    pass


class RateLimitUnavailable(RuntimeError):
    pass


class RateLimiter:
    def __init__(self) -> None:
        self._redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

    @staticmethod
    def _safe_identifier(identifier: str) -> str:
        return hashlib.sha256(identifier.encode("utf-8")).hexdigest()

    def enforce(self, scope: str, identifier: str, *, limit: int, window_seconds: int) -> None:
        if limit < 1 or window_seconds < 1:
            raise ValueError("Rate limit configuration must be positive")
        key = f"rate:{scope}:{self._safe_identifier(identifier)}"
        try:
            count = self._redis.incr(key)
            if count == 1:
                self._redis.expire(key, window_seconds)
            if count > limit:
                raise RateLimitExceeded("Too many requests. Try again shortly.")
        except RateLimitExceeded:
            raise
        except RedisError as exc:
            if settings.APP_ENV == "development":
                return
            raise RateLimitUnavailable("Rate-limit storage is unavailable") from exc


rate_limiter = RateLimiter()
