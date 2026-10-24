import pytest

from app.core.config import AuthMode, Settings
from app.services.registration_service import RegistrationError, issue_session


@pytest.mark.asyncio
async def test_keycloak_mode_rejects_legacy_password_grant_bridge():
    settings = Settings(auth_mode=AuthMode.KEYCLOAK, otp_test_mode=False)
    with pytest.raises(RegistrationError) as error:
        await issue_session(None, settings, registration_token="opaque-test-token")
    assert error.value.status_code == 409
    assert error.value.code == "oidc_required"
