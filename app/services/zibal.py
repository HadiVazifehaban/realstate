"""Fail-closed HTTP adapter for the Zibal payment gateway.

The adapter deliberately returns normalized, minimal fields. Raw gateway bodies
are never logged or persisted because they can contain masked card information.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

import httpx

from app.core.config import NodeMode, Settings


class ZibalError(RuntimeError):
    """Base class for sanitized gateway errors."""

    code = "zibal_error"
    uncertain = False


class ZibalNotConfigured(ZibalError):
    code = "zibal_not_configured"


class ZibalDeclined(ZibalError):
    """Zibal returned a definitive non-success result."""

    code = "zibal_declined"


class ZibalUncertain(ZibalError):
    """The request may have reached Zibal but no conclusive response arrived."""

    code = "zibal_result_unknown"
    uncertain = True


@dataclass(frozen=True)
class ZibalStartedPayment:
    track_id: str
    payment_url: str
    result_code: int


@dataclass(frozen=True)
class ZibalVerifiedPayment:
    track_id: str
    status: str
    amount_rial: int | None
    reference_id: str
    result_code: int
    source: str


def _valid_http_url(value: str, *, allow_local_http: bool) -> bool:
    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme not in ({"https", "http"} if allow_local_http else {"https"}):
            return False
        if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            return False
        if parsed.scheme == "http":
            if not allow_local_http:
                return False
            try:
                return parsed.hostname.lower() == "localhost" or ipaddress.ip_address(parsed.hostname).is_loopback
            except ValueError:
                return False
        return True
    except (TypeError, ValueError):
        return False


def validate_zibal_web_urls(settings: Settings, *, callback_url: str, result_url: str) -> None:
    local_http = settings.node_mode is NodeMode.LOCAL
    if not _valid_http_url(callback_url, allow_local_http=local_http):
        raise ZibalNotConfigured("نشانی Callback زیبال معتبر نیست.")
    if not urlsplit(callback_url.strip()).path.rstrip("/").endswith("/api/v1/billing/zibal/callback"):
        raise ZibalNotConfigured("Callback باید مستقیماً به Endpoint عمومی Billing شکارچی اشاره کند.")
    if not _valid_http_url(result_url, allow_local_http=local_http):
        raise ZibalNotConfigured("نشانی بازگشت کاربر از زیبال معتبر نیست.")


class ZibalPaymentProvider:
    """Zibal request/verify/inquiry adapter using server-side credentials only."""

    SUCCESS_RESULT = 100
    ALREADY_VERIFIED_RESULT = 201
    PAID_INQUIRY_STATUS = 1

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    def ensure_ready(self) -> None:
        settings = self.settings
        gateway_urls = (
            settings.zibal_request_url,
            settings.zibal_verify_url,
            settings.zibal_inquiry_url,
            settings.zibal_start_url,
        )
        for url in gateway_urls:
            parsed = urlsplit(url.strip())
            if (
                parsed.scheme != "https"
                or parsed.hostname != "gateway.zibal.ir"
                or parsed.username
                or parsed.password
                or parsed.fragment
            ):
                raise ZibalNotConfigured("نشانی API زیبال باید از دامنهٔ رسمی و HTTPS باشد.")
        if not settings.zibal_enabled or not settings.zibal_merchant.strip():
            raise ZibalNotConfigured("درگاه زیبال فعال یا پیکربندی نشده است.")
        validate_zibal_web_urls(
            settings,
            callback_url=settings.zibal_callback_url,
            result_url=settings.zibal_result_url,
        )

    async def _post(self, url: str, payload: dict) -> dict:
        self.ensure_ready()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.zibal_timeout_seconds),
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                response = await client.post(url, json=payload)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ZibalUncertain("پاسخ قطعی از زیبال دریافت نشد.") from exc
        except httpx.RequestError as exc:
            raise ZibalUncertain("ارتباط با زیبال نامشخص ماند.") from exc

        if response.status_code >= 500:
            raise ZibalUncertain("سرویس زیبال موقتاً پاسخ قطعی نداد.")
        if response.status_code != 200:
            raise ZibalDeclined("درخواست پرداخت توسط زیبال پذیرفته نشد.")
        try:
            result = response.json()
        except ValueError as exc:
            raise ZibalUncertain("پاسخ زیبال قابل‌خواندن نبود.") from exc
        if not isinstance(result, dict):
            raise ZibalUncertain("ساختار پاسخ زیبال معتبر نبود.")
        return result

    @staticmethod
    def _result_code(response: dict) -> int:
        try:
            return int(response.get("result", -1))
        except (TypeError, ValueError):
            return -1

    async def create_payment(
        self,
        *,
        amount_rial: int,
        order_number: str,
        description: str,
    ) -> ZibalStartedPayment:
        if amount_rial <= 0:
            raise ValueError("مبلغ پرداخت زیبال باید مثبت باشد.")
        response = await self._post(
            self.settings.zibal_request_url,
            {
                "merchant": self.settings.zibal_merchant.strip(),
                "amount": amount_rial,
                "callbackUrl": self.settings.zibal_callback_url,
                "description": description[:255],
                "orderId": order_number[:64],
            },
        )
        result_code = self._result_code(response)
        if result_code != self.SUCCESS_RESULT:
            raise ZibalDeclined("زیبال درخواست پرداخت را نپذیرفت.")
        track_value = response.get("trackId")
        if isinstance(track_value, bool) or not isinstance(track_value, (int, str)):
            raise ZibalUncertain("زیبال شناسهٔ قابل‌پیگیری برنگرداند.")
        track_id = str(track_value).strip()
        if not track_id or len(track_id) > 64:
            raise ZibalUncertain("شناسهٔ برگشتی زیبال معتبر نیست.")
        base = self.settings.zibal_start_url.rstrip("/")
        return ZibalStartedPayment(
            track_id=track_id,
            payment_url=f"{base}/{quote(track_id, safe='')}",
            result_code=result_code,
        )

    async def verify_payment(self, *, track_id: str) -> ZibalVerifiedPayment:
        response = await self._post(
            self.settings.zibal_verify_url,
            {"merchant": self.settings.zibal_merchant.strip(), "trackId": track_id},
        )
        result_code = self._result_code(response)
        if result_code == self.ALREADY_VERIFIED_RESULT:
            return await self.inquire_payment(track_id=track_id)
        if result_code != self.SUCCESS_RESULT:
            raise ZibalDeclined("تأیید پرداخت توسط زیبال موفق نبود.")
        return self._normalize_paid_response(response, track_id=track_id, source="verify", status="PAID")

    async def inquire_payment(self, *, track_id: str) -> ZibalVerifiedPayment:
        response = await self._post(
            self.settings.zibal_inquiry_url,
            {"merchant": self.settings.zibal_merchant.strip(), "trackId": track_id},
        )
        result_code = self._result_code(response)
        if result_code != self.SUCCESS_RESULT:
            raise ZibalDeclined("استعلام پرداخت زیبال موفق نبود.")
        try:
            status = int(response.get("status", -1))
        except (TypeError, ValueError):
            status = -1
        if status != self.PAID_INQUIRY_STATUS:
            return ZibalVerifiedPayment(
                track_id=track_id,
                status="PENDING",
                amount_rial=None,
                reference_id="",
                result_code=result_code,
                source="inquiry",
            )
        return self._normalize_paid_response(response, track_id=track_id, source="inquiry", status="PAID")

    @staticmethod
    def _normalize_paid_response(
        response: dict,
        *,
        track_id: str,
        source: str,
        status: str,
    ) -> ZibalVerifiedPayment:
        try:
            amount_rial = int(response["amount"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ZibalUncertain("مبلغ تأییدشده در پاسخ زیبال موجود یا معتبر نیست.") from exc
        if amount_rial <= 0:
            raise ZibalUncertain("مبلغ تأییدشدهٔ زیبال معتبر نیست.")
        reference = response.get("refNumber") or response.get("refnumber") or ""
        return ZibalVerifiedPayment(
            track_id=track_id,
            status=status,
            amount_rial=amount_rial,
            reference_id=str(reference)[:128],
            result_code=ZibalPaymentProvider._result_code(response),
            source=source,
        )
