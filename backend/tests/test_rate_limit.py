import pytest
from redis.exceptions import RedisError

from app.core.config import settings
from app.services.rate_limit import RateLimitExceeded, RateLimitUnavailable, RateLimiter


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expiries = {}

    def incr(self, key):
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def expire(self, key, seconds):
        self.expiries[key] = seconds
        return True


class BrokenRedis:
    def incr(self, key):
        raise RedisError("down")


def test_rate_limiter_sets_window_and_rejects_above_limit():
    limiter = RateLimiter()
    fake = FakeRedis()
    limiter._redis = fake

    limiter.enforce("maps", "user-1", limit=2, window_seconds=60)
    limiter.enforce("maps", "user-1", limit=2, window_seconds=60)
    with pytest.raises(RateLimitExceeded):
        limiter.enforce("maps", "user-1", limit=2, window_seconds=60)

    assert list(fake.expiries.values()) == [60]


def test_rate_limiter_fails_closed_outside_development(monkeypatch):
    limiter = RateLimiter()
    limiter._redis = BrokenRedis()
    monkeypatch.setattr(settings, "APP_ENV", "production")
    with pytest.raises(RateLimitUnavailable):
        limiter.enforce("maps", "user-1", limit=2, window_seconds=60)
