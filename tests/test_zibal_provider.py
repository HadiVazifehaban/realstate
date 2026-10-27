from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import NodeMode, Settings
from app.services.zibal import ZibalDeclined, ZibalNotConfigured, ZibalPaymentProvider, ZibalUncertain


def zibal_settings(**changes) -> Settings:
    values = dict(
        node_mode=NodeMode.CLOUD_HUB,
        zibal_enabled=True,
        zibal_test_mode=True,
        zibal_merchant="sandbox-merchant",
        zibal_callback_url="https://api.shekarchi.example/api/v1/billing/zibal/callback",
        zibal_result_url="https://app.shekarchi.example/dashboard/billing",
    )
    values.update(changes)
    return Settings(**values)


@pytest.mark.asyncio
async def test_create_payment_converts_payload_in_rials_and_constructs_trusted_url() -> None:
    calls: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"result": 100, "trackId": 123456})

    provider = ZibalPaymentProvider(zibal_settings(), transport=httpx.MockTransport(handler))
    result = await provider.create_payment(
        amount_rial=12_340_000,
        order_number="SHK-260101-ABC-1",
        description="SHEKARCHI subscription",
    )

    assert calls == [{
        "merchant": "sandbox-merchant",
        "amount": 12_340_000,
        "callbackUrl": "https://api.shekarchi.example/api/v1/billing/zibal/callback",
        "description": "SHEKARCHI subscription",
        "orderId": "SHK-260101-ABC-1",
    }]
    assert result.track_id == "123456"
    assert result.payment_url == "https://gateway.zibal.ir/start/123456"


@pytest.mark.asyncio
async def test_verify_requires_positive_exact_gateway_amount_field() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"result": 100, "amount": 12_340_000, "refNumber": 998877})

    provider = ZibalPaymentProvider(zibal_settings(), transport=httpx.MockTransport(handler))
    result = await provider.verify_payment(track_id="123456")
    assert result.status == "PAID"
    assert result.amount_rial == 12_340_000
    assert result.reference_id == "998877"


@pytest.mark.asyncio
async def test_already_verified_result_uses_inquiry_and_does_not_assume_paid() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/verify"):
            return httpx.Response(200, json={"result": 201})
        return httpx.Response(200, json={"result": 100, "status": 0})

    provider = ZibalPaymentProvider(zibal_settings(), transport=httpx.MockTransport(handler))
    result = await provider.verify_payment(track_id="123456")
    assert calls == ["/v1/verify", "/v1/inquiry"]
    assert result.status == "PENDING"
    assert result.amount_rial is None


@pytest.mark.asyncio
async def test_gateway_decline_and_transport_timeout_are_not_success() -> None:
    async def declined(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"result": 103})

    provider = ZibalPaymentProvider(zibal_settings(), transport=httpx.MockTransport(declined))
    with pytest.raises(ZibalDeclined):
        await provider.create_payment(amount_rial=1000, order_number="SHK-ORDER-1", description="test")

    async def timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout")

    provider = ZibalPaymentProvider(zibal_settings(), transport=httpx.MockTransport(timeout))
    with pytest.raises(ZibalUncertain):
        await provider.create_payment(amount_rial=1000, order_number="SHK-ORDER-1", description="test")


def test_provider_is_double_opt_in_and_rejects_http_gateway_or_wrong_callback() -> None:
    with pytest.raises(ZibalNotConfigured):
        ZibalPaymentProvider(Settings()).ensure_ready()
    with pytest.raises(ZibalNotConfigured):
        ZibalPaymentProvider(zibal_settings(zibal_request_url="http://gateway.zibal.ir/v1/request")).ensure_ready()
    with pytest.raises(ZibalNotConfigured):
        ZibalPaymentProvider(zibal_settings(zibal_callback_url="https://app.shekarchi.example/callback")).ensure_ready()
