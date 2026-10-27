"""Stealth HTTP client for delta.ir, plus the RSC-flight JSON-LD extractor.

Why this file is unusual
-----------------------
Every other source in this package talks to a JSON API. Delta has none: it is a
Next.js app whose listing data is serialised into the React Server Component
(flight) payload of the rendered HTML. There is no ``<script type="application/
ld+json">`` on the page -- the structured data is embedded one level deeper, as a
string inside a ``self.__next_f.push([...])`` call. So the client has to do two
jobs that the other clients do not: fetch a page, and dig a JSON object back out
of JavaScript.

The extraction procedure, in order:

1. Pull every ``self.__next_f.push([...])`` argument array out of the HTML.
2. ``json.loads`` each array -- these are real JSON, so the string payloads come
   back already unescaped -- and concatenate the strings. That concatenation is
   what reassembles flight rows that were split across pushes.
3. Locate the configured row marker (``28:``) and slice from there to the next
   hexadecimal row marker.
4. Unescape one further quoting layer -- the JSON-LD is itself a JSON *string*
   inside the flight row, so it arrives double-encoded.
5. Walk braces from the first ``{`` to find the matching close, then
   ``json.loads`` the slice.

Step 3 tolerates Delta moving the row id: :func:`extract_detail_jsonld` scans
every row and returns the first whose payload parses as a schema.org Product, so
a deploy that renumbers the rows degrades to a slower scan rather than to zero
listings. Verified against live pages 2026-10; see ``probe_delta.py``.

IMAGE URLS EXPIRE
-----------------
Delta serves photos as presigned S3 links carrying ``X-Amz-Expires=86400`` --
24 hours. Storing the URL in ``property_media.cloud_url`` would leave a dead
gallery the next day, so the ingestion pipeline downloads each photo to
``data/media`` at ingest time and stores the served path instead. See
``app/services/ingestion/pipeline.py``.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.logging import get_logger
from app.services.scraper.delta_taxonomy import (
    normalise_city,
    normalise_deal_type,
    normalise_property_type,
)
from app.services.scraper.divar_client import ScraperResponseError, StealthClient

logger = get_logger("app.scraper.delta")

#: Matches ``self.__next_f.push([1,"..."])`` up to the closing ``])``. The
#: payload is JSON, so a non-greedy match to the first ``]);`` is safe.
_FLIGHT_PUSH_RE = re.compile(r"self\.__next_f\.push\((\[.*?\])\)", re.DOTALL)

#: Flight rows are ``<id>:<payload>`` where the id is a hex counter. Used both to
#: find the row we want and to find where it ends.
_FLIGHT_ROW_RE = re.compile(r"(?:^|\n)([0-9a-f]{1,4}):(?=[^\n])")


def _flight_text(html: str) -> str:
    """Concatenate every ``__next_f.push`` string payload into one blob."""
    chunks: list[str] = []
    for match in _FLIGHT_PUSH_RE.finditer(html):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            # A push chunk can be truncated by a streaming response boundary.
            logger.debug("delta: unparseable flight chunk, skipping")
            continue
        if isinstance(payload, list) and len(payload) > 1:
            for part in payload[1:]:
                if isinstance(part, str):
                    chunks.append(part)
    return "".join(chunks)


def _candidate_rows(flight: str, preferred_row: str) -> list[str]:
    """Yield row payloads, the configured one first.

    Delta renumbers flight rows between deploys, so the preferred id is a hint
    rather than a contract: every other row is still offered to the caller as a
    fallback.
    """
    rows: list[tuple[int, str]] = []
    for match in _FLIGHT_ROW_RE.finditer(flight):
        row_id = match.group(1)
        start = match.end()
        rows.append((0 if row_id == preferred_row.rstrip(":") else 1, start))

    # Slice each row up to the next row marker.
    ordered = sorted(rows, key=lambda item: item[0])
    out: list[str] = []
    for _, start in ordered:
        nxt = _FLIGHT_ROW_RE.search(flight, start)
        end = nxt.start() if nxt else len(flight)
        out.append(flight[start:end])
    return out


def _balanced_object(text: str) -> str | None:
    """Return the first balanced ``{...}`` span, or ``None`` if unbalanced.

    Brace counting is naive about braces inside strings, which JSON-LD titles and
    descriptions do contain. That is acceptable here because the result is fed
    to :func:`json.loads` afterwards: a mis-count simply fails to parse and the
    caller moves to the next row.
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def extract_detail_jsonld(html: str, *, preferred_row: str = "28:") -> dict[str, Any]:
    """Recover the listing's schema.org payload from a rendered Delta page.

    Returns the parsed object, or ``{}`` when the page carries no parseable
    listing -- a sold listing, a login wall, or a layout change.
    """
    flight = _flight_text(html)
    if not flight:
        return {}

    for row in _candidate_rows(flight, preferred_row):
        # The JSON-LD arrives JSON-encoded inside the row, so peel one string
        # layer before brace counting.
        for candidate in (row, _unescape_once(row)):
            blob = _balanced_object(candidate)
            if not blob:
                continue
            try:
                parsed = json.loads(blob)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and parsed.get("@type") == "Product":
                return parsed
    return {}


def _unescape_once(text: str) -> str:
    """Undo one round of JSON string escaping.

    ``\\\\\\"`` -> ``"``, so the row's quoted payload becomes bare JSON that the
    brace scanner can read.
    """
    return text.replace('\\"', '"').replace("\\\\", "\\")


class DeltaClient(StealthClient):
    """Async client for delta.ir.

    Inherits pacing, TLS impersonation, retries, and proxy rotation from
    :class:`StealthClient`; only the endpoints and the HTML parsing are Delta's.
    """

    #: Property/deal type of the most recent ``search`` call.
    #:
    #: Delta's canonical detail URL is ``/detail/{id}``, which carries no type
    #: segment, so the type a listing was found under is only known from the
    #: search that produced it. A job runs search-then-details on one client
    #: instance, so caching it here and stamping it onto each detail payload is
    #: enough -- and it keeps the shared ``parse_detail(payload, token)`` dispatch
    #: signature unchanged, which every other source depends on.
    _last_search_context: dict[str, str] | None = None

    # ------------------------------------------------------------------ search
    async def search(
        self,
        city: str,
        category: str,
        page: int = 1,
        districts: list[str] | tuple[str, ...] | None = None,
    ) -> dict:
        """Fetch one page of Delta search results.

        Delta routes search by ``/{city}/{deal}/{property-type}``, so the Divar
        ``apartment-sell`` category slug has to be split into its two halves.
        Returns ``{"listing_ids": [...], "url": ...}`` -- the list page carries
        no structured data, only the links to the detail pages.
        """
        deal_slug, type_slug = self._split_category(category)
        url = (
            f"{self.settings.delta_web_base_url}"
            f"{self.settings.delta_search_path.format(city=city, deal=deal_slug, property_type=type_slug)}"
        )
        # Delta paginates with ?page=, 1-based.
        params: dict[str, Any] = {"page": page}
        self._last_search_context = {
            "city": city,
            "deal": deal_slug,
            "property_type": type_slug,
        }
        response = await self._request("GET", url, params=params)
        html = response.text
        return {"listing_ids": extract_listing_ids(html), "url": url, "html": html,
                "city": city}

    def _split_category(self, category: str) -> tuple[str, str]:
        """Map a Divar-style ``apartment-sell`` slug onto Delta's two segments.

        Falls back to the bare property type when the category carries no deal
        marker, which keeps a single-type job (``land``) working unchanged.
        """
        slug = (category or "").strip().lower()
        for marker, deal in (("-sell", "buy"), ("-rent", "rent"), ("-mortgage", "mortgage")):
            if slug.endswith(marker):
                return deal, normalise_property_type(slug[: -len(marker)])
        return "buy", normalise_property_type(slug)

    # ------------------------------------------------------------------ detail
    async def get_post(self, token: str) -> dict:
        """Fetch and decode one Delta detail page into a listing dict.

        The node normalises all five Delta detail URL shapes down to the bare id
        (see ``delta_taxonomy.listing_id_from_url``), so a single
        ``/detail/{id}`` template covers every one of them.
        """
        listing_id = normalise_listing_id(token)
        url = self.settings.delta_web_base_url + self.settings.delta_detail_path.format(
            listing_id=listing_id
        )
        response = await self._request("GET", url)
        payload = extract_detail_jsonld(
            response.text, preferred_row=self.settings.delta_flight_row
        )
        if not payload:
            raise ScraperResponseError(
                f"no listing JSON-LD in Delta response for {url}"
            )
        payload.setdefault("__url", url)
        if self._last_search_context:
            payload["__context"] = dict(self._last_search_context)
        return payload

    # Alias so Delta satisfies the same duck-typed interface the pipeline uses.
    get_listing = get_post


_LISTING_LINK_RE = re.compile(r"/detail/(\d+)")


def extract_listing_ids(html: str) -> list[str]:
    """Collect detail-page ids from a rendered Delta list page, de-duplicated."""
    seen: set[str] = set()
    out: list[str] = []
    for match in _LISTING_LINK_RE.finditer(html):
        listing_id = match.group(1)
        if listing_id not in seen:
            seen.add(listing_id)
            out.append(listing_id)
    return out


def normalise_listing_id(token: str) -> str:
    """Reduce any accepted token to Delta's numeric listing id."""
    from app.services.scraper.delta_taxonomy import listing_id_from_url

    value = (token or "").strip()
    if value.isdigit():
        return value
    from_url = listing_id_from_url(value)
    if from_url:
        return from_url
    if "/" in value:
        return value.rstrip("/").rsplit("/", 1)[-1]
    raise ValueError(f"{token!r} is not a Delta listing id or detail URL")


__all__ = [
    "DeltaClient",
    "extract_detail_jsonld",
    "extract_listing_ids",
    "normalise_city",
    "normalise_deal_type",
    "normalise_property_type",
]