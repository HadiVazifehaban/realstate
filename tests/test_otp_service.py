"""Unit tests for the SHEKARCHI OTP challenge lifecycle.

No Redis, Keycloak or live SMS gateway is required: explicit test mode uses an
in-process TTL dict and the OTP HMAC helper is deterministic.
"""

from __future__ import annotations

import pytest
import asyncio

from app.core.config import Settings
from app.core.mobile import MobileError, normalize_mobile
from app.services import otp_service
from app.services.otp_service import (
    OtpVerifyResult,
    hash_code,
    mint_code,
    mint_token,
    request_otp,
    reset_store,
    verify_otp,
)

_TEST_OTP_HMAC_SECRET = "unit-test-only-otp-hmac-secret-32-bytes"


def _empty_settings(**overrides):
    """A Settings pointing at a dedicated test Redis database."""
    base = dict(
        otp_test_mode=True,
        otp_hmac_secret=_TEST_OTP_HMAC_SECRET,
        otp_ttl_seconds=120,
        otp_max_attempts=3,
        otp_request_cooldown_seconds=120,
        otp_max_requests_per_hour=10,
        otp_max_requests_per_ip_hour=30,
        registration_token_ttl_minutes=15,
        mobile_verified_grace_seconds=1800,
        new_user_pii_quota=0,
        professional_allowed_roles=(
            "ROLE_JUNIOR_BROKER,ROLE_SENIOR_BROKER,ROLE_AGENCY_MANAGER,ROLE_DATA_ANALYST"
        ),
        analyst_invite_code="",
        redis_url="",
    )
    base.update(overrides)
    return Settings(**base)


def _reset():
    """Discard the process-global store so each case starts clean."""
    reset_store()


@pytest.fixture(autouse=True)
def _clean_otp_redis() -> None:
    """Use the explicitly enabled test-only in-memory backend."""
    _reset()
    yield


# --------------------------------------------------------------------------- #
# Mobile normalization
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("09121234567", "+989121234567"),
        ("+989121234567", "+989121234567"),
        ("00989121234567", "+989121234567"),
        ("+98 912 123 45 67", "+989121234567"),
        ("0912 1234567", "+989121234567"),
        ("0912-123-4567", "+989121234567"),
    ],
)
def test_normalize_mobile(raw, expected):
    assert normalize_mobile(raw) == expected


@pytest.mark.parametrize(
    "bad",
    ["", "0912123", "091212345678", "1234567890", "021912123456", "+98912345"],
)
def test_normalize_mobile_rejects_invalid(bad):
    with pytest.raises(MobileError):
        normalize_mobile(bad)


# --------------------------------------------------------------------------- #
# Crypto helpers
# --------------------------------------------------------------------------- #


def test_hash_code_is_deterministic():
    value = hash_code("123456", "+989121234567", _TEST_OTP_HMAC_SECRET)
    assert value == hash_code("123456", "+989121234567", _TEST_OTP_HMAC_SECRET)
    assert "123456" not in value
    assert value != hash_code("123456", "+989121234567", "another-test-secret-32-bytes-long")


@pytest.mark.parametrize("code", ["000000", "999999", "123456"])
def test_mint_code_is_six_ascii_digits(code):
    assert len(mint_code()) == 6
    assert mint_code().isdigit()


def test_mint_token_is_url_safe_and_random():
    samples = {mint_token() for _ in range(25)}
    assert len(samples) == 25
    for token in samples:
        assert len(token) > 30
        assert all(c.isalnum() or c in "-_" for c in token)


# --------------------------------------------------------------------------- #
# OTP request + verify (in-memory store)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_request_otp_sends_challenge_and_returns_dev_code():
    settings = _empty_settings()
    _reset()
    result = await request_otp(settings, "+989121234567", purpose="login")
    assert result.ok is True
    assert result.dev_code is not None
    assert len(result.dev_code) == 6
    assert result.dev_code.isdigit()


@pytest.mark.asyncio
async def test_request_otp_enforces_cooldown_and_hourly_budget():
    settings = _empty_settings(
        otp_request_cooldown_seconds=2,
        otp_max_requests_per_hour=5,
        otp_max_requests_per_ip_hour=5,
    )
    _reset()
    first = await request_otp(settings, "+989121234567", purpose="login")
    assert first.ok is True

    second = await request_otp(settings, "+989121234567", purpose="login")
    assert second.ok is False
    assert second.retry_after >= 1

    for _ in range(4):
        await request_otp(settings, "+989121234567", purpose="login")
    overloaded = await request_otp(settings, "+989121234567", purpose="login")
    assert overloaded.ok is False


@pytest.mark.asyncio
async def test_request_otp_enforces_daily_hard_limit():
    settings = _empty_settings(otp_max_requests_per_day=1)
    mobile = "+989121234567"
    result = await request_otp(settings, mobile, purpose="registration")
    assert result.ok is True
    store = otp_service.get_store(settings)
    await store.delete(store.key("cooldown", mobile))

    limited = await request_otp(settings, mobile, purpose="registration")
    assert limited.ok is False
    assert limited.retry_after > 0


@pytest.mark.asyncio
async def test_verify_otp_accepts_correct_code_and_mints_token():
    settings = _empty_settings()
    _reset()
    result = await request_otp(settings, "+989121234567", purpose="login")
    assert result.ok is True

    token = await verify_otp(settings, "+989121234567", result.dev_code)
    assert isinstance(token, OtpVerifyResult)
    assert token.ok is True
    assert len(token.registration_token) > 30
    assert token.registration_token != result.dev_code


@pytest.mark.asyncio
async def test_verify_otp_rejects_wrong_code_and_keeps_challenge():
    settings = _empty_settings()
    _reset()
    result = await request_otp(settings, "+989121234567", purpose="login")
    assert result.ok is True

    wrong = await verify_otp(settings, "+989121234567", "000000")
    assert isinstance(wrong, OtpVerifyResult)
    assert wrong.ok is False
    assert wrong.reason == "invalid"

    again = await verify_otp(settings, "+989121234567", result.dev_code)
    assert again.ok is True


@pytest.mark.asyncio
async def test_three_wrong_attempts_consume_the_challenge():
    settings = _empty_settings()
    result = await request_otp(settings, "+989121234567", purpose="login")
    assert result.ok is True

    for _ in range(3):
        assert (await verify_otp(settings, "+989121234567", "000000")).ok is False
    assert (await verify_otp(settings, "+989121234567", result.dev_code)).ok is False


@pytest.mark.asyncio
async def test_concurrent_wrong_attempts_cannot_bypass_attempt_cap():
    settings = _empty_settings()
    mobile = "+989121234567"
    result = await request_otp(settings, mobile, purpose="registration")
    assert result.ok is True

    outcomes = await asyncio.gather(
        *(verify_otp(settings, mobile, "000000") for _ in range(8))
    )
    assert all(not outcome.ok for outcome in outcomes)
    assert (await verify_otp(settings, mobile, result.dev_code)).ok is False


@pytest.mark.asyncio
async def test_concurrent_otp_requests_issue_only_one_challenge():
    settings = _empty_settings()
    mobile = "+989121234567"
    outcomes = await asyncio.gather(
        *(request_otp(settings, mobile, purpose="registration") for _ in range(12))
    )
    assert sum(outcome.ok for outcome in outcomes) == 1
    assert all(outcome.retry_after > 0 for outcome in outcomes if not outcome.ok)


@pytest.mark.asyncio
async def test_otp_hmac_secret_is_required_outside_test_mode():
    settings = _empty_settings(otp_test_mode=False, otp_hmac_secret="")
    with pytest.raises(Exception, match="OTP signing secret is not configured"):
        await request_otp(settings, "+989121234567", purpose="login")


@pytest.mark.asyncio
async def test_verify_otp_does_not_leak_account_existence():
    settings = _empty_settings()
    _reset()
    pending = await request_otp(settings, "+989121234567", purpose="login")
    assert pending.ok is True

    unknown = await verify_otp(settings, "+989121234567", "999999")
    assert unknown.ok is False

    different = await request_otp(settings, "+989123456789", purpose="login")
    assert different.ok is True


@pytest.mark.asyncio
async def test_verify_otp_consumes_token_exactly_once():
    settings = _empty_settings()
    _reset()
    result = await request_otp(settings, "+989121234567", purpose="login")
    assert result.ok is True
    first = await verify_otp(settings, "+989121234567", result.dev_code)
    assert first.ok is True
    token = first.registration_token

    replay = await verify_otp(settings, "+989121234567", result.dev_code)
    assert replay.ok is False
    assert replay.registration_token == ""


@pytest.mark.asyncio
async def test_consume_registration_token_is_single_use():
    settings = _empty_settings()
    _reset()
    result = await request_otp(settings, "+989121234567", purpose="login")
    assert result.ok is True
    first = await verify_otp(settings, "+989121234567", result.dev_code)
    assert first.ok is True
    token = first.registration_token

    from app.services.otp_service import consume_registration_token

    mobile = await consume_registration_token(settings, token)
    assert mobile == "+989121234567"
    reused = await consume_registration_token(settings, token)
    assert reused is None


@pytest.mark.asyncio
async def test_is_mobile_verified_after_consumption():
    settings = _empty_settings()
    _reset()
    result = await request_otp(settings, "+989121234567", purpose="login")
    assert result.ok is True
    await verify_otp(settings, "+989121234567", result.dev_code)

    from app.services.otp_service import is_mobile_verified

    assert await is_mobile_verified(settings, "+989121234567") is True
