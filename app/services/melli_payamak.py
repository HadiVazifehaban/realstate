"""MelliPayamak REST pattern SMS adapter.

The adapter never retries a POST: a timeout can mean the gateway accepted the
message even though the response was lost. Body IDs are deployment config and
remain disabled until the corresponding panel patterns are approved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Protocol

import httpx

from app.core.config import Settings
from app.services.sms_provider import SmsError


class SmsProviderError(SmsError):
    """Safe-to-report delivery failure; never contains request credentials."""


class SmsHttpError(SmsProviderError):
    """Gateway returned a non-success HTTP status."""


class SmsBusinessError(SmsProviderError):
    """Gateway accepted HTTP but rejected the SMS operation."""


class SmsProviderProtocol(Protocol):
    async def send_otp(self, mobile_e164: str, code: str) -> str: ...


@dataclass(frozen=True)
class SmsSendResult:
    message_id: str
    ret_status: int


@dataclass(frozen=True)
class Pattern:
    body_setting: str
    variables: tuple[str, ...]


PATTERN_REGISTRY: Mapping[str, Pattern] = {
    "shekarchi_otp_login": Pattern("sms_melli_otp_body_id", ("code",)),
    # Panel-confirmed product name; retain the prior identifier for compatibility.
    "shekarchi_otp": Pattern("sms_melli_otp_body_id", ("code",)),
    "shekarchi_visit_booking": Pattern("sms_melli_visit_body_id", ("property_id", "date", "time")),
    "shekarchi_price_alert": Pattern("sms_melli_price_alert_body_id", ("region", "price")),
    # Current panel request groups lead/price alerts under the same approved template.
    "shekarchi_lead_alert": Pattern("sms_melli_price_alert_body_id", ("region", "price")),
    "shekarchi_agency_sub": Pattern("sms_melli_agency_sub_body_id", ("plan_name", "expire_date")),
}
_PHONE = re.compile(r"^\+989\d{9}$")
_BODY_ID = re.compile(r"^[1-9]\d{0,9}$")
_SAFE_VARIABLE = re.compile(r"^[^;{}\r\n]{1,128}$")
_BUSINESS_ERRORS = {
    -112: "webservice_disabled", -111: "ip_not_allowed", -110: "api_key_required",
    -109: "allowed_ip_required", -108: "ip_blocked", -10: "links_not_allowed",
    -6: "provider_internal_error", -5: "pattern_variables_mismatch",
    -4: "body_id_invalid_or_unapproved", -3: "sender_line_missing",
    -2: "single_recipient_only", -1: "pattern_service_disabled", 0: "credentials_invalid",
    2: "insufficient_credit", 6: "provider_maintenance", 7: "filtered_content",
    10: "account_inactive", 11: "delivery_rejected", 12: "account_documents_incomplete",
    18: "phone_invalid", 19: "daily_api_limit_reached",
}


class MelliPayamakConfig:
    def __init__(self, settings: Settings):
        if not settings.mellipayamak_enabled:
            raise ValueError("MelliPayamak delivery is disabled pending pattern approval")
        self.username = settings.sms_melli_username.strip()
        self.password = settings.sms_melli_password
        self.endpoint = settings.sms_melli_endpoint.strip()
        self.timeout = settings.sms_melli_timeout_seconds
        self.sms_melli_otp_body_id = settings.sms_melli_otp_body_id
        if not self.username or not self.password:
            raise ValueError("MelliPayamak is enabled but username/password are not configured")
        parsed = httpx.URL(self.endpoint)
        if parsed.scheme != "https" and parsed.host not in {"127.0.0.1", "localhost", "testserver"}:
            raise ValueError("MelliPayamak endpoint must use HTTPS")
        if not 0.1 <= self.timeout <= 60:
            raise ValueError("MelliPayamak timeout is outside the allowed range")


class MelliPayamakSmsSenderProvider:
    def __init__(self, config: MelliPayamakConfig, client: httpx.AsyncClient):
        self._config = config
        self._client = client

    async def send_pattern(self, to: str, body_id: str, variables: Mapping[str, str], *, pattern_id: str) -> SmsSendResult:
        if not _PHONE.fullmatch(to):
            raise SmsProviderError("Invalid mobile number")
        pattern = PATTERN_REGISTRY.get(pattern_id)
        if pattern is None:
            raise SmsProviderError("Unknown SMS pattern")
        if not _BODY_ID.fullmatch(str(body_id or "")):
            raise SmsProviderError("SMS pattern is disabled: approved Body ID is missing")
        if set(variables) != set(pattern.variables):
            raise SmsProviderError("SMS pattern variables do not match the required names")
        vals = tuple(str(variables[name]) for name in pattern.variables)
        if any(not _SAFE_VARIABLE.fullmatch(value) for value in vals):
            raise SmsProviderError("SMS pattern contains an invalid variable")
        # REST documentation defines `text` as ordered values separated by ';'.
        payload = {"username": self._config.username, "password": self._config.password,
                   "text": ";".join(vals), "to": to[1:], "bodyId": int(body_id)}
        try:
            response = await self._client.post(self._config.endpoint, json=payload)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            # Deliberately no retry: request acceptance may be unknown.
            raise SmsProviderError("SMS gateway request failed") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise SmsHttpError(f"SMS gateway HTTP failure ({response.status_code})")
        try:
            data = response.json()
            ret_status = int(data.get("RetStatus"))
            value = str(data.get("Value", ""))
        except (ValueError, TypeError, AttributeError):
            raise SmsProviderError("SMS gateway returned an invalid response") from None
        if ret_status != 1 or not value.isdigit() or len(value) < 16:
            code = int(value) if value.lstrip("-").isdigit() else ret_status
            reason = _BUSINESS_ERRORS.get(code, "provider_rejected")
            raise SmsBusinessError(f"SMS gateway rejected the request ({reason})")
        return SmsSendResult(message_id=value, ret_status=ret_status)

    async def send_otp(self, mobile_e164: str, code: str) -> str:
        body_id = getattr(self._config, "sms_melli_otp_body_id", "")
        result = await self.send_pattern(mobile_e164, body_id, {"code": code}, pattern_id="shekarchi_otp_login")
        return result.message_id


class MelliPayamakSmsSenderProviderFactory:
    """Creates one pooled, TLS-verifying HTTP client for app lifespan."""
    def __init__(self, settings: Settings, *, client: httpx.AsyncClient | None = None):
        self.config = MelliPayamakConfig(settings)
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout), verify=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            follow_redirects=False,
        )
        self.provider = MelliPayamakSmsSenderProvider(self.config, self.client)

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()


def body_id_for(settings: Settings, pattern_id: str) -> str:
    pattern = PATTERN_REGISTRY.get(pattern_id)
    if pattern is None:
        raise SmsProviderError("Unknown SMS pattern")
    return str(getattr(settings, pattern.body_setting, "") or "")
