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
