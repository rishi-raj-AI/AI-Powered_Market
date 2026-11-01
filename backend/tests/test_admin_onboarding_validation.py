"""Pre-registration does not confer verified status or administrator privileges."""
import pytest
from pydantic import ValidationError

from app.api.v1.routes.admin_onboarding import UserOnboardRequest
from app.models.user import UserRole


def test_onboarding_requires_international_phone():
    with pytest.raises(ValidationError):
        UserOnboardRequest(phone="9999999999", full_name="Test Rider", role=UserRole.DELIVERY)
    with pytest.raises(ValidationError):
        UserOnboardRequest(phone="+91bad", full_name="Test Rider", role=UserRole.DELIVERY)
    with pytest.raises(ValidationError):
        UserOnboardRequest(phone="+15551234567", full_name="Test Rider", role=UserRole.DELIVERY)


def test_onboarding_accepts_valid_roles_without_verifying():
    for role in (UserRole.CUSTOMER, UserRole.MERCHANT, UserRole.DELIVERY):
        payload = UserOnboardRequest(phone="+919876543210", full_name="Test User", role=role)
        assert payload.role == role


def test_onboarding_rejects_blank_name():
    with pytest.raises(ValidationError):
        UserOnboardRequest(phone="+919876543210", full_name="", role=UserRole.CUSTOMER)


def test_phone_onboarding_only_when_phone_login_can_verify_ownership(monkeypatch):
    from app.api.v1.routes import admin_onboarding
    for provider, sms_enabled, expected in (
        ("local_otp", True, True),
        ("msg91_widget", True, True),
        ("firebase", True, False),
        ("firebase", False, False),
        ("local_otp", False, False),
    ):
        monkeypatch.setattr(admin_onboarding.settings, "AUTH_PROVIDER", provider)
        monkeypatch.setattr(admin_onboarding.settings, "SMS_AUTH_ENABLED", sms_enabled)
        assert admin_onboarding._phone_onboarding_enabled() is expected


def test_firebase_only_pre_registration_rejected_before_database_write(monkeypatch):
    from unittest.mock import MagicMock
    from fastapi import HTTPException
    from app.api.v1.routes import admin_onboarding
    monkeypatch.setattr(admin_onboarding.settings, "AUTH_PROVIDER", "firebase")
    monkeypatch.setattr(admin_onboarding.settings, "SMS_AUTH_ENABLED", False)
    db = MagicMock()
    payload = UserOnboardRequest(phone="+919876543210", full_name="Test Rider", role=UserRole.DELIVERY)
    with pytest.raises(HTTPException) as exc:
        admin_onboarding.admin_onboard_user(payload, MagicMock(), db, MagicMock())
    assert exc.value.status_code == 409
    db.add.assert_not_called()
    db.commit.assert_not_called()
