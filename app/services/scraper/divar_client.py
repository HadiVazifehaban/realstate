"""Stealth HTTP transport shared by every listing source (Divar, Sheypoor, ...).

Uses ``curl_cffi`` to impersonate real browser TLS/JA3 fingerprints, which
defeats Cloudflare / Arvan / Divar TLS fingerprinting.  Requests are paced with
randomised delays and retried with exponential + jittered backoff, and support a
rotating outbound proxy pool.

Source-specific clients only add endpoint methods; pacing, retries and proxy
rotation live here so a second source cannot quietly diverge on rate limiting.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.scraper import cities

logger = get_logger("app.scraper.client")


class ScraperError(RuntimeError):
    """Base class for scraper failures."""


class ScraperBlockedError(ScraperError):
    """The remote endpoint is actively blocking us (403/429/5xx)."""


class ScraperResponseError(ScraperError):
    """A non-retryable HTTP error response."""


class StealthClient:
    """Paced, retrying, proxied HTTP client for public listing APIs.

    A ``session`` may be injected (tests, connection pooling).  When omitted a
    ``curl_cffi`` ``AsyncSession`` is created lazily and owned by the client.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        session: Any | None = None,
        rng: random.Random | None = None,
        sleep: Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._session = session
        self._owns_session = session is None
        self._rng = rng or random.Random()
        self._sleep = sleep or asyncio.sleep
        self._proxy_index = 0
        self._request_count = 0

    # ------------------------------------------------------------------ context
    async def __aenter__(self) -> "StealthClient":
        await self._ensure_session()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    async def _ensure_session(self) -> Any:
        if self._session is None:
            from curl_cffi.requests import AsyncSession

            self._session = AsyncSession(
                impersonate=self.settings.scraper_impersonate,
                timeout=self.settings.scraper_timeout_seconds,
            )
        return self._session

    async def aclose(self) -> None:
        if self._owns_session and self._session is not None:
            close = getattr(self._session, "close", None)
            if close is not None:
                result = close()
                if asyncio.iscoroutine(result):
                    await result
            self._session = None

    # -------------------------------------------------------------- proxy / pace
    def _next_proxy(self) -> dict[str, str] | None:
        pool = self.settings.proxy_list
        if not pool:
            return None
        proxy = pool[self._proxy_index % len(pool)]
        self._proxy_index += 1
        if "://" not in proxy:
            proxy = f"http://{proxy}"
        return {"http": proxy, "https": proxy}

    def backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with multiplicative jitter."""
        base = self.settings.scraper_base_backoff_seconds
        cap = self.settings.scraper_backoff_max_seconds
        delay = min(base * (2**attempt), cap)
        jitter = delay * self.settings.scraper_jitter_factor
        return max(0.0, delay + self._rng.uniform(-jitter, jitter))

    def pace_delay(self) -> float:
        """Random pacing delay inserted between consecutive requests."""
        lo = self.settings.scraper_pace_min_seconds
        hi = max(lo, self.settings.scraper_pace_max_seconds)
        return self._rng.uniform(lo, hi)

    async def _throttle(self) -> None:
        if self._request_count > 0:
            await self._sleep(self.pace_delay())
        self._request_count += 1


    # ---------------------------------------------------------------- transport
    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
        headers: dict | None = None,
    ) -> Any:
        session = await self._ensure_session()
        max_retries = self.settings.scraper_max_retries
        last_exc: Exception | None = None

        for attempt in range(max_retries + 1):
            await self._throttle()
            try:
                response = await session.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers=headers,
                    proxies=self._next_proxy(),
                    timeout=self.settings.scraper_timeout_seconds,
                    impersonate=self.settings.scraper_impersonate,
                )
                status = getattr(response, "status_code", 0)
                if status in (403, 429) or status >= 500:
                    if attempt < max_retries:
                        await self._sleep(self.backoff_delay(attempt))
                        continue
                    raise ScraperBlockedError(f"HTTP {status} for {url}")
                if status >= 400:
                    raise ScraperResponseError(f"HTTP {status} for {url}")
                return response
            except ScraperResponseError:
                raise
            except ScraperError as exc:
                last_exc = exc
                if attempt < max_retries:
                    await self._sleep(self.backoff_delay(attempt))
                    continue
                raise
            except Exception as exc:  # noqa: BLE001 - network layer
                last_exc = exc
                if attempt < max_retries:
                    await self._sleep(self.backoff_delay(attempt))
                    continue
                raise ScraperError(f"Request to {url} failed: {exc}") from exc

        raise ScraperError(f"Request to {url} failed: {last_exc}")


class DivarClient(StealthClient):
    """Async, anti-detection client for Divar's public web API.

    Only the endpoints are Divar-specific; pacing, retries and proxy rotation
    are inherited from :class:`StealthClient`.
    """

    # --------------------------------------------------------------- endpoints
    def _search_payload(
        self,
        city: str,
        category: str,
        page: int,
        districts: list[str] | tuple[str, ...] | None = None,
    ) -> dict:
        """Build the POST /v8/postlist/w/search body.

        The API layer needs numeric ids, not the web-layer slugs, so the
        city/district are resolved through the registry. Unknown values raise
        before any request is made.
        """
        entry = cities.get_city(city)
        if not entry.is_verified:
            logger.warning(
                "divar city id for %r is unverified; refresh the registry "
                "(app.cli.divar_cities) if this search returns no results",
                city,
            )
        # Filters nest under form_data.data; putting them directly under
        # form_data is accepted but silently dropped (the API echoes back
        # "form_data": {} and returns unfiltered listings).
        form_data: dict[str, Any] = {
            "data": {"category": {"str": {"value": category}}},
        }
        if districts:
            district_ids = cities.resolve_district_ids(entry.slug, list(districts))
            form_data["data"]["district"] = {"int": {"value": district_ids}}
        return {
            # city_ids are TYPE_STRING on the wire -- sending the bare int the
            # registry stores is rejected with
            # "city_ids[0]: invalid value 1 for type TYPE_STRING".
            "city_ids": [str(entry.city_id)],
            "pagination_data": {
                # Full protobuf type URL, package-qualified. The bare
                # "PageNumber" fails with "type URLs must be of the form
                # 'type.googleapis.com/<typename>'", and omitting the
                # `post_list.` package fails with "unknown type: PageNumber".
                "@type": "type.googleapis.com/post_list.PaginationData",
                "page": page,
                "page_size": self.settings.scraper_page_size,
            },
            "search_data": {"form_data": form_data},
        }

    async def search(
        self,
        city: str,
        category: str,
        page: int = 1,
        districts: list[str] | tuple[str, ...] | None = None,
    ) -> dict:
        """Fetch one page of the Divar post list (raw JSON)."""
        url = f"{self.settings.divar_api_base_url}/v8/postlist/w/search"
        response = await self._request(
            "POST",
            url,
            json=self._search_payload(city, category, page, districts),
            headers={"Content-Type": "application/json"},
        )
        return response.json()

    async def get_post(self, token: str) -> dict:
        """Fetch the full detail payload for a single listing."""
        url = f"{self.settings.divar_api_base_url}/v8/posts-v2/web/{token}"
        response = await self._request("GET", url)
        return response.json()

    async def get_contact_info(self, token: str) -> dict:
        """Fetch owner contact info (requires an authenticated session/OTP)."""
        url = f"{self.settings.divar_api_base_url}/v8/postcontact/web/contact_info/{token}"
        response = await self._request("GET", url)
        return response.json()
