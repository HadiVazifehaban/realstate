from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.core.config import AuthMode, Settings
from app.schemas.registration import VerifiedRegistrationIn
from app.services import registration_service as service


@pytest.fixture
def setup(monkeypatch):
    settings = Settings(auth_mode=AuthMode.KEYCLOAK, otp_test_mode=False)
    store = SimpleNamespace(key=lambda *args: ":".join(args), set=AsyncMock(return_value=True),
                            compare_and_delete=AsyncMock(return_value=True))
    session = SimpleNamespace(add=lambda obj: None, commit=AsyncMock())
    proof = AsyncMock(return_value="+989120000001")
    create = AsyncMock(return_value=SimpleNamespace(id="new-user"))
    monkeypatch.setattr(service, "consume_registration_token", proof)
    monkeypatch.setattr(service, "get_store", lambda settings: store)
    monkeypatch.setattr(service.keycloak_admin, "username_exists", AsyncMock(return_value=False))
    monkeypatch.setattr(service.keycloak_admin, "find_user_by_phone", AsyncMock(return_value=None))
    monkeypatch.setattr(service.keycloak_admin, "create_mobile_user", create)
    return settings, store, session, proof, create


async def register(setup):
    return await service.register_verified_account(
        setup[2], setup[0], registration_token="opaque-verified-token-value",
        username="chosen.name", first_name="نام", last_name="خانوادگی", password="SecurePass12!",
    )


@pytest.mark.asyncio
async def test_preserves_chosen_username_and_only_grants_base_role(setup):
    result = await register(setup)
    assert result["username"] == "chosen.name"
    kwargs = setup[4].await_args.kwargs
    assert kwargs["username"] == "chosen.name"
    assert kwargs["mobile_e164"] == "+989120000001"
    assert kwargs["role"].value == "USER"
    assert kwargs["kyc_status"] == "PENDING"
    assert kwargs["password"] == "SecurePass12!"
    setup[1].compare_and_delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_expired_or_replayed_proof_never_creates_account(setup):
    setup[3].return_value = None
    with pytest.raises(service.RegistrationError, match="منقضی"):
        await register(setup)
    setup[4].assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_username_rejected_server_side(setup):
    service.keycloak_admin.username_exists.return_value = True
    with pytest.raises(service.RegistrationError) as error:
        await register(setup)
    assert error.value.code == "username_taken"
    assert error.value.status_code == 409
    assert "نام کاربری تکراری است" in error.value.message
    setup[4].assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_mobile_cannot_be_reassigned(setup):
    service.keycloak_admin.find_user_by_phone.return_value = object()
    with pytest.raises(service.RegistrationError) as error:
        await register(setup)
    assert error.value.code == "mobile_registered"
    setup[4].assert_not_awaited()


@pytest.mark.asyncio
async def test_keycloak_uniqueness_race_returns_conflict(setup):
    setup[4].side_effect = service.KeycloakDirectoryError(409, "duplicate_user", "duplicate")
    with pytest.raises(service.RegistrationError) as error:
        await register(setup)
    assert error.value.status_code == 409
    assert error.value.code == "username_taken"
    assert "نام کاربری تکراری است" in error.value.message


@pytest.mark.asyncio
async def test_parallel_mobile_registration_is_blocked(setup):
    setup[1].set.return_value = False
    with pytest.raises(service.RegistrationError) as error:
        await register(setup)
    assert error.value.code == "registration_in_progress"
    setup[4].assert_not_awaited()


@pytest.mark.parametrize("username", ["ab", "name space", "../admin", "نام", "x" * 65])
def test_invalid_username_is_rejected(username):
    with pytest.raises(ValidationError):
        VerifiedRegistrationIn(registration_token="x" * 32, username=username,
                               first_name="نام", last_name="خانوادگی", password="SecurePass12!")


def test_client_cannot_assign_privileged_role():
    with pytest.raises(ValidationError):
        VerifiedRegistrationIn(registration_token="x" * 32, username="chosen.name",
                               first_name="نام", last_name="خانوادگی", password="SecurePass12!", role="ADMIN")


@pytest.mark.asyncio
async def test_fake_sms_is_not_allowed_outside_explicit_test_mode():
    from app.services.otp_service import request_otp
    from app.services.sms_provider import SmsError

    settings = Settings(otp_test_mode=False, sms_provider="fake", otp_hmac_secret="s" * 32)
    with pytest.raises(SmsError, match="Real SMS delivery"):
        await request_otp(settings, "+989120000001")


@pytest.mark.parametrize("existing, requested, expected", [
    ("chosen.name", "chosen.name", True),
    ("chosen.name", "CHOSEN.NAME", True),
    ("chosen.name.other", "chosen.name", False),
])
@pytest.mark.asyncio
async def test_username_lookup_requires_exact_case_insensitive_match(monkeypatch, existing, requested, expected):
    api = AsyncMock(return_value=[{"username": existing}])
    monkeypatch.setattr(service.keycloak_admin, "_api", api)
    settings = Settings()
    assert await service.keycloak_admin.username_exists(settings, requested) is expected
    api.assert_awaited_once_with(settings, "GET", "/users", params={"username": requested, "exact": "true"})


@pytest.mark.parametrize("password", ["", "short", "x" * 129])
def test_registration_rejects_invalid_password_length(password):
    with pytest.raises(ValidationError):
        VerifiedRegistrationIn(registration_token="x" * 32, username="chosen.name",
                               first_name="نام", last_name="خانوادگی", password=password)


def test_registration_password_is_redacted_and_preserved():
    body = VerifiedRegistrationIn(registration_token="x" * 32, username="chosen.name",
                                  first_name="نام", last_name="خانوادگی", password=" SecurePass12! ")
    assert body.password.get_secret_value() == " SecurePass12! "
    assert "SecurePass12!" not in repr(body)


@pytest.mark.asyncio
async def test_password_is_provisioned_in_same_request_as_account(monkeypatch):
    kc = service.keycloak_admin
    send = AsyncMock(return_value=SimpleNamespace(headers={"location": "http://keycloak/users/new-user"}))
    monkeypatch.setattr(kc, "_send", send)
    monkeypatch.setattr(kc, "_set_realm_roles", AsyncMock())
    monkeypatch.setattr(kc, "get_user", AsyncMock(return_value=SimpleNamespace(id="new-user")))
    await kc.create_mobile_user(Settings(), mobile_e164="+989120000001", username="chosen.name", password="SecurePass12!")
    payload = send.await_args.kwargs["json_body"]
    assert payload["credentials"] == [{"type": "password", "value": "SecurePass12!", "temporary": False}]
    assert payload["username"] == "chosen.name"