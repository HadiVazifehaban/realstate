from __future__ import annotations

import asyncio
import logging

import httpx
import pytest

from app.core.config import Settings
from app.services.melli_payamak import (
    MelliPayamakSmsSenderProviderFactory,
    SmsBusinessError,
    SmsHttpError,
    SmsProviderError,
)


def configured(**kwargs):
    values = {
        "sms_melli_username": "test-user", "sms_melli_password": "never-log-me",
        "sms_melli_endpoint": "https://gateway.test/api/SendSMS/BaseServiceNumber",
        "sms_melli_otp_body_id": "12345",
        "mellipayamak_enabled": True,
    }
    values.update(kwargs)
    return Settings(**values)


@pytest.mark.asyncio
async def test_success_json_contract_and_registry_order():
    seen = []
    async def handler(request):
        seen.append((request.headers["content-type"], request.read(), request.url.path))
        return httpx.Response(200, json={"Value": "12345678901234567", "RetStatus": 1, "StrRetStatus": "Ok"})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    factory = MelliPayamakSmsSenderProviderFactory(configured(), client=client)
    result = await factory.provider.send_pattern(
        "+989121234567", "12345", {"time": "14:30", "property_id": "A-9", "date": "1405/07/27"},
        pattern_id="shekarchi_visit_booking",
    )
    import json
    assert result.message_id == "12345678901234567"
    assert seen[0][0].startswith("application/json")
    body = json.loads(seen[0][1])
    assert body == {"username": "test-user", "password": "never-log-me", "text": "A-9;1405/07/27;14:30", "to": "989121234567", "bodyId": 12345}
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
async def test_http_errors_are_classified_without_retry(status):
    calls = 0
    async def handler(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(status, text="sensitive response")
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    factory = MelliPayamakSmsSenderProviderFactory(configured(), client=client)
    with pytest.raises(SmsHttpError):
        await factory.provider.send_otp("+989121234567", "123456")
    assert calls == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_business_error_timeout_connection_and_invalid_json():
    async def business(_): return httpx.Response(200, json={"Value": "-4", "RetStatus": 0, "StrRetStatus": "bad"})
    client = httpx.AsyncClient(transport=httpx.MockTransport(business))
    provider = MelliPayamakSmsSenderProviderFactory(configured(), client=client).provider
    with pytest.raises(SmsBusinessError, match="body_id_invalid_or_unapproved"):
        await provider.send_otp("+989121234567", "123456")
    await client.aclose()

    async def bad_json(_): return httpx.Response(200, text="not-json")
    client = httpx.AsyncClient(transport=httpx.MockTransport(bad_json))
    provider = MelliPayamakSmsSenderProviderFactory(configured(), client=client).provider
    with pytest.raises(SmsProviderError, match="invalid response"):
        await provider.send_otp("+989121234567", "123456")
    await client.aclose()

    async def timeout(_): raise httpx.ReadTimeout("otp=123456 password=secret")
    client = httpx.AsyncClient(transport=httpx.MockTransport(timeout))
    provider = MelliPayamakSmsSenderProviderFactory(configured(), client=client).provider
    with pytest.raises(SmsProviderError, match="request failed") as err:
        await provider.send_otp("+989121234567", "123456")
    assert "123456" not in str(err.value)
    await client.aclose()

    async def connection_error(_): raise httpx.ConnectError("credential=secret")
    client = httpx.AsyncClient(transport=httpx.MockTransport(connection_error))
    provider = MelliPayamakSmsSenderProviderFactory(configured(), client=client).provider
    with pytest.raises(SmsProviderError, match="request failed") as err:
        await provider.send_otp("+989121234567", "123456")
    assert "secret" not in str(err.value)
    await client.aclose()


@pytest.mark.asyncio
async def test_validation_missing_body_and_pattern_variables():
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"Value": "12345678901234567", "RetStatus": 1})))
    provider = MelliPayamakSmsSenderProviderFactory(configured(sms_melli_otp_body_id=""), client=client).provider
    with pytest.raises(SmsProviderError, match="Body ID"):
        await provider.send_otp("+989121234567", "123456")
    with pytest.raises(SmsProviderError, match="mobile"):
        await provider.send_pattern("09121234567", "123", {"code": "123"}, pattern_id="shekarchi_otp_login")
    with pytest.raises(SmsProviderError, match="variable"):
        await provider.send_pattern("+989121234567", "123", {"extra": "x"}, pattern_id="shekarchi_otp_login")
    with pytest.raises(SmsProviderError, match="invalid variable"):
        await provider.send_pattern("+989121234567", "123", {"code": "x;y"}, pattern_id="shekarchi_otp_login")
    await client.aclose()


@pytest.mark.asyncio
async def test_approved_panel_aliases_use_same_contract_without_enabling_delivery():
    from app.services.melli_payamak import PATTERN_REGISTRY

    assert PATTERN_REGISTRY["shekarchi_otp"] == PATTERN_REGISTRY["shekarchi_otp_login"]
    assert PATTERN_REGISTRY["shekarchi_lead_alert"] == PATTERN_REGISTRY["shekarchi_price_alert"]
    assert Settings(_env_file=None).mellipayamak_enabled is False


def test_unknown_sms_provider_fails_closed_instead_of_falling_back_to_fake():
    from app.services.sms_provider import SmsError, get_sms_provider

    with pytest.raises(SmsError, match="not supported"):
        get_sms_provider(Settings(_env_file=None, sms_provider="melli-payak"))


def test_environment_aliases_match_the_shared_mellipayamak_configuration(monkeypatch):
    monkeypatch.setenv("MELLIPAYAMAK_ENABLED", "true")
    monkeypatch.setenv("MELLIPAYAMAK_OTP_BODY_ID", "mock-body-id")
    monkeypatch.setenv("MELLIPAYAMAK_LEAD_BODY_ID", "mock-lead-id")
    settings = Settings(_env_file=None)
    assert settings.mellipayamak_enabled is True
    assert settings.sms_melli_otp_body_id == "mock-body-id"
    assert settings.sms_melli_price_alert_body_id == "mock-lead-id"


def test_provider_factory_refuses_to_construct_while_delivery_disabled():
    with pytest.raises(ValueError, match="disabled pending pattern approval"):
        MelliPayamakSmsSenderProviderFactory(configured(mellipayamak_enabled=False))


@pytest.mark.asyncio
async def test_concurrent_requests_share_client_and_factory_closes_owned_client():
    calls = 0
    async def handler(_):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return httpx.Response(200, json={"Value": str(10**16 + calls), "RetStatus": 1})
    factory = MelliPayamakSmsSenderProviderFactory(configured())
    factory.client._transport = httpx.MockTransport(handler)
    ids = await asyncio.gather(*[factory.provider.send_otp("+989121234567", f"{i:06d}") for i in range(12)])
    assert calls == 12 and len(ids) == 12
    client = factory.client
    await factory.aclose()
    assert client.is_closed


def test_factory_rejects_missing_credentials():
    with pytest.raises(ValueError, match="username/password"):
        MelliPayamakSmsSenderProviderFactory(Settings(_env_file=None, mellipayamak_enabled=True))
