import pytest

from app.core.config import AuthMode, Settings
from app.services.registration_service import (
    RegistrationError,
    issue_session,
    quick_register,
    submit_professional,
)


@pytest.mark.asyncio
async def test_keycloak_mode_rejects_legacy_password_grant_bridge():
    settings = Settings(auth_mode=AuthMode.KEYCLOAK, otp_test_mode=False)
    with pytest.raises(RegistrationError) as error:
        await issue_session(None, settings, registration_token="opaque-test-token")
    assert error.value.status_code == 409
    assert error.value.code == "oidc_required"


@pytest.mark.asyncio
async def test_keycloak_mode_rejects_parallel_quick_registration():
    settings = Settings(auth_mode=AuthMode.KEYCLOAK, otp_test_mode=False)
    with pytest.raises(RegistrationError) as error:
        await quick_register(None, settings, registration_token="opaque-test-token")
    assert error.value.status_code == 409
    assert error.value.code == "oidc_registration_required"


@pytest.mark.asyncio
async def test_keycloak_mode_rejects_parallel_professional_registration():
    settings = Settings(auth_mode=AuthMode.KEYCLOAK, otp_test_mode=False)
    with pytest.raises(RegistrationError) as error:
        await submit_professional(
            None,
            settings,
            registration_token="opaque-test-token",
            requested_role="ROLE_JUNIOR_BROKER",
            first_name="آزمایشی",
            last_name="کاربر",
            email="",
            cities=[],
            payload={},
        )
    assert error.value.status_code == 409
    assert error.value.code == "oidc_registration_required"
