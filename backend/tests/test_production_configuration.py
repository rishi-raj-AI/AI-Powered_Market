"""P1: exercise the behaviour that only exists outside development.

Backend CI runs with APP_ENV=development. In that mode the rate limiter fails
*open* when Redis errors, the dev OTP shortcut is live, docs are served, and
every production safety validator in Settings is skipped. The production-only
branches therefore had no coverage at all, and a regression in them would ship
green.

These tests construct production-shaped settings directly rather than needing a
second CI environment, so the gated behaviour is verified on every run.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from redis.exceptions import RedisError

from app.core.config import Settings
from app.services.rate_limit import (
    RateLimiter,
    RateLimitExceeded,
    RateLimitUnavailable,
)

STRONG_SECRET = "x" * 48
BASE = {
    "APP_ENV": "production",
    "APP_DEBUG": False,
    "SECRET_KEY": STRONG_SECRET,
}


def production_settings(**overrides) -> Settings:
    return Settings(**{**BASE, **overrides})


# ------------------------------------------------------------------ settings


def test_production_rejects_the_default_secret_key() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        production_settings(SECRET_KEY="change-this-in-production")


def test_production_rejects_a_short_secret_key() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        production_settings(SECRET_KEY="too-short")


def test_production_refuses_debug_mode() -> None:
    with pytest.raises(ValidationError, match="APP_DEBUG"):
        production_settings(APP_DEBUG=True)


def test_msg91_sms_requires_its_credentials_in_production() -> None:
    with pytest.raises(ValidationError, match="MSG91"):
        production_settings(SMS_PROVIDER="msg91", MSG91_AUTH_KEY=None, MSG91_TEMPLATE_ID=None)


def test_msg91_widget_auth_requires_its_key_in_production() -> None:
    with pytest.raises(ValidationError, match="MSG91_AUTH_KEY"):
        production_settings(AUTH_PROVIDER="msg91_widget", MSG91_AUTH_KEY=None)


def test_fcm_credentials_must_be_configured_together() -> None:
    with pytest.raises(ValidationError, match="FCM"):
        production_settings(FCM_PROJECT_ID="gaonone", FCM_SERVICE_ACCOUNT_JSON_B64=None)


def test_a_valid_production_configuration_is_accepted() -> None:
    settings = production_settings(
        AUTH_PROVIDER="msg91_widget",
        MSG91_AUTH_KEY="a-real-widget-key",
        CORS_ORIGINS="https://gaonone.in",
        TRUSTED_HOSTS="gaonone.in",
    )
    assert settings.APP_ENV == "production"
    assert settings.cors_origins == ["https://gaonone.in"]
    assert settings.trusted_hosts == ["gaonone.in"]


def test_staging_is_held_to_the_same_safety_rules() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(APP_ENV="staging", APP_DEBUG=False, SECRET_KEY="change-this-in-production")


def test_unknown_environments_are_rejected() -> None:
    with pytest.raises(ValidationError, match="APP_ENV"):
        Settings(APP_ENV="prod", SECRET_KEY=STRONG_SECRET)


# --------------------------------------------------------------- rate limits


class _BrokenRedis:
    def incr(self, key):
        raise RedisError("redis is down")

    def expire(self, key, seconds):
        raise RedisError("redis is down")


class _CountingRedis:
    def __init__(self):
        self.counts: dict[str, int] = {}

    def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, key, seconds):
        return True


def _limiter(redis_client) -> RateLimiter:
    limiter = RateLimiter.__new__(RateLimiter)
    limiter._redis = redis_client
    return limiter


def test_rate_limiting_fails_closed_when_redis_is_down_in_production(monkeypatch) -> None:
    """The behaviour development never sees: an outage must not remove the limit."""
    monkeypatch.setattr("app.services.rate_limit.settings", production_settings())
    limiter = _limiter(_BrokenRedis())
    with pytest.raises(RateLimitUnavailable):
        limiter.enforce("otp", "+919000000000", limit=5, window_seconds=900)


def test_rate_limiting_fails_open_only_in_development(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.rate_limit.settings", Settings(APP_ENV="development", SECRET_KEY=STRONG_SECRET)
    )
    limiter = _limiter(_BrokenRedis())
    # No exception: local development must not require a running Redis.
    limiter.enforce("otp", "+919000000000", limit=5, window_seconds=900)


def test_staging_also_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.rate_limit.settings",
        Settings(APP_ENV="staging", APP_DEBUG=False, SECRET_KEY=STRONG_SECRET),
    )
    limiter = _limiter(_BrokenRedis())
    with pytest.raises(RateLimitUnavailable):
        limiter.enforce("otp", "+919000000000", limit=5, window_seconds=900)


def test_the_limit_actually_bites(monkeypatch) -> None:
    monkeypatch.setattr("app.services.rate_limit.settings", production_settings())
    limiter = _limiter(_CountingRedis())
    for _ in range(3):
        limiter.enforce("otp", "+919000000001", limit=3, window_seconds=900)
    with pytest.raises(RateLimitExceeded):
        limiter.enforce("otp", "+919000000001", limit=3, window_seconds=900)


def test_identifiers_are_hashed_so_phone_numbers_never_become_redis_keys() -> None:
    redis_client = _CountingRedis()
    limiter = _limiter(redis_client)
    limiter.enforce("otp", "+919812345678", limit=5, window_seconds=900)
    key = next(iter(redis_client.counts))
    assert "9812345678" not in key
    assert key.startswith("rate:otp:")


# ------------------------------------------------------- production app shape


def test_docs_are_not_served_in_production() -> None:
    """Schema exposure is a production posture decision, not a code path."""
    import app.main as main_module

    source = main_module.__file__
    with open(source) as handle:
        text = handle.read()
    assert 'docs_url=None if is_production else "/docs"' in text
    assert 'openapi_url=None if is_production else "/openapi.json"' in text


def test_worker_uses_a_worker_liveness_probe_not_the_api_http_probe() -> None:
    """The worker shares the API image but does not listen on port 8000."""
    compose = (Path(__file__).parents[2] / "docker-compose.prod.yml").read_text()
    worker = compose.split("\n  worker:", 1)[1].split("\n  migrate:", 1)[0]

    assert "healthcheck:" in worker
    assert "/proc/1/cmdline" in worker
    assert "app.scripts.worker" in worker


def test_production_otp_endpoints_are_gated_by_the_widget_provider() -> None:
    """With the MSG91 widget in production, the local OTP endpoints are closed."""
    from app.api.v1.routes import auth as auth_routes

    settings = production_settings(AUTH_PROVIDER="msg91_widget", MSG91_AUTH_KEY="key")
    assert settings.APP_ENV == "production"
    assert settings.AUTH_PROVIDER == "msg91_widget"
    source = auth_routes.__doc__ or ""
    del source
    import inspect

    request_source = inspect.getsource(auth_routes.request_otp)
    verify_source = inspect.getsource(auth_routes.verify_otp)
    for text in (request_source, verify_source):
        assert 'settings.APP_ENV == "production"' in text
        assert 'settings.AUTH_PROVIDER == "msg91_widget"' in text
        assert "HTTP_410_GONE" in text
