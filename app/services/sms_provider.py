"""SMS provider adapters for OTP delivery.

Contract: :meth:`SmsProvider.send_otp` sends a one-time code and returns a
provider message id (or ``"fake-..."`` in test mode). Nothing here ever logs
the code -- see ``otp_service`` for the audit rules.

Providers
---------
* ``fake``   -- in-process outbox (``OTP_TEST_MODE`` / ``sms_provider=fake``).
                Local dev + test-suite only; never wired in production.
* ``kavenegar`` -- Kavenegar Lookup API (OTP template). Needs ``sms_api_key``
                (+ optional ``sms_sender`` template name) in production.
"""

from __future__ import annotations

import time
from typing import Protocol

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger("app.otp.sms")

_FAKE_OUTBOX: dict[str, dict[str, str]] = {}


class SmsError(RuntimeError):
    """The provider refused or the gateway was unreachable."""


class SmsProvider(Protocol):
    async def send_otp(self, mobile_e164: str, code: str) -> str:
        """Send ``code``; return the provider message id."""
        ...


def last_fake_code(mobile_e164: str) -> str | None:
    """Last code the fake adapter accepted (tests only)."""
    return (_FAKE_OUTBOX.get(mobile_e164) or {}).get("code")


class FakeSmsProvider:
    """In-process outbox; records sends so tests assert the flow."""

    async def send_otp(self, mobile_e164: str, code: str) -> str:
        message_id = f"fake-{int(time.time() * 1000)}"
        _FAKE_OUTBOX[mobile_e164] = {"code": code, "id": message_id}
        return message_id


class DisabledSmsProvider:
    """Fail closed when a real provider is selected but not approved/enabled."""

    def __init__(self, reason: str = "SMS provider is disabled") -> None:
        self._reason = reason

    async def send_otp(self, mobile_e164: str, code: str) -> str:
        raise SmsError(self._reason)


class KavenegarSmsProvider:
    """Kavenegar Lookup (OTP template) delivery.

    ``POST {base}/verify/lookup.json`` with ``receptor``, ``token``,
    ``template``. ``sms_base_url`` overrides the API root (tests pin it to
    loopback); ``sms_sender`` selects the template, default ``shekarchi-otp``.
    """

    _DEFAULT_BASE = "https://api.kavenegar.com/v1"
    _DEFAULT_TEMPLATE = "shekarchi-otp"

    def __init__(self, settings: Settings) -> None:
        self._api_key = (settings.sms_api_key or "").strip()
        self._template = (settings.sms_sender or "").strip() or self._DEFAULT_TEMPLATE
        base = (settings.sms_base_url or "").strip().rstrip("/")
        self._base = base or self._DEFAULT_BASE

    async def send_otp(self, mobile_e164: str, code: str) -> str:
        import httpx

        if not self._api_key:
            raise SmsError("کلید پیامک تنظیم نشده است.")
        receptor = mobile_e164[1:] if mobile_e164.startswith("+") else mobile_e164
        url = f"{self._base}/{self._api_key}/verify/lookup.json"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    url,
                    data={"receptor": receptor, "token": code, "template": self._template},
                )
        except Exception as exc:
            raise SmsError("ارتباط با سرویس پیامک برقرار نشد.") from exc
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        entries = ((payload or {}).get("return") or {}).get("status")
        message_id = ""
        try:
            first = (payload.get("entries") or [{}])[0]
            message_id = str(first.get("messageid") or "")
        except (AttributeError, IndexError, TypeError):
            message_id = ""
        if response.status_code != 200 or entries != 200:
            logger.error("kavenegar lookup failed: http=%s", response.status_code)
            raise SmsError("ارسال پیامک ناموفق بود.")
        return message_id or f"kavenegar-{int(time.time() * 1000)}"


def get_sms_provider(settings: Settings) -> SmsProvider:
    """Select the adapter from ``sms_provider`` (``fake`` unless configured)."""
    name = (settings.sms_provider or "fake").strip().lower()
    if name == "kavenegar":
        return KavenegarSmsProvider(settings)
    if name == "fake":
        return FakeSmsProvider()
    if name == "melli-payamak":
        raise SmsError("MelliPayamak provider must be initialized by application lifespan")
    raise SmsError("Configured SMS provider is not supported")


__all__ = [
    "FakeSmsProvider",
    "KavenegarSmsProvider",
    "SmsError",
    "SmsProvider",
    "get_sms_provider",
    "last_fake_code",
]
