"""On-demand owner phone extraction (session / OTP gated).

Metadata scraping is always allowed; phone numbers are only fetched when an
authenticated Divar session is available (``PHONE_EXTRACTION_ENABLED=true``).
Extracted numbers are cached (Redis or in-memory) and handed straight to the
Phase 1 encrypted PII vault — never stored in a public column.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.scraper.cache import TokenCache
from app.services.scraper.parser import iter_dicts, normalize_digits

logger = get_logger("app.scraper.phone")

_PHONE_RE = re.compile(r"(?:0|\+?98)?9\d{2}\d{3}\d{4}")
_PHONE_KEYS = ("phone", "phone_number", "mobile", "cellphone", "value", "number")


def parse_phone(payload: Any) -> str | None:
    """Extract a normalised 11-digit Iranian mobile number from any payload."""
    for node in iter_dicts(payload):
        for key in _PHONE_KEYS:
            value = node.get(key)
            if not isinstance(value, str):
                continue
            match = _PHONE_RE.search(normalize_digits(value).replace(" ", "").replace("-", ""))
            if match:
                return _normalize(match.group(0))

    # Last-resort: regex across the whole serialised payload.
    text = normalize_digits(str(payload)).replace(" ", "").replace("-", "")
    match = _PHONE_RE.search(text)
    return _normalize(match.group(0)) if match else None


def _normalize(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("98") and len(digits) == 12:
        digits = "0" + digits[2:]
    if digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits
    # Persian digits are 11 long starting with 09.
    if len(digits) == 10:
        digits = "0" + digits
    return digits


class PhoneExtractor:
    """Fetches + caches owner phone numbers behind an authenticated session."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: Any | None = None,
        cache: TokenCache | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client
        self._cache = cache or TokenCache(self.settings.redis_url)
        # Explicit opt-in for tests / callers; otherwise fall back to settings.
        self._enabled_override: bool | None = enabled

    @property
    def enabled(self) -> bool:
        if self._enabled_override is not None:
            return self._enabled_override
        return bool(self.settings.phone_extraction_enabled)

    async def extract(self, token: str, *, client: Any | None = None) -> str | None:
        """Return the owner's phone for ``token`` or ``None``.

        Returns ``None`` (a deliberate stub) unless phone extraction is enabled
        and an authenticated client is supplied — this keeps the default
        commercial build fully compliant/metadata-only.
        """
        if not self.enabled:
            return None

        cache_key = f"phone:{token}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        active_client = client or self._client
        if active_client is None:
            return None

        try:
            payload = await active_client.get_contact_info(token)
        except Exception as exc:  # noqa: BLE001 - never break ingestion
            logger.warning("phone extraction failed for %s: %s", token, exc)
            return None

        phone = parse_phone(payload)
        if phone:
            await self._cache.set(
                cache_key, phone, ttl=self.settings.phone_cache_ttl_seconds
            )
        return phone
