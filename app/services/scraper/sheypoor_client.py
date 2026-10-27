"""Stealth HTTP client for Sheypoor.

ENDPOINT PROVENANCE — READ BEFORE TRUSTING THE DEFAULTS
-------------------------------------------------------
The defaults here were **verified against the live site on 2026-10-05** and
replaced an earlier guess that never worked: the previous client requested
``/api/web/v1/search/{city}/real-estate``, which answers 404, so the one Sheypoor
job this node ever ran failed with a bare HTTP 404 and the portal's feed stayed
empty.

What actually exists:

* ``GET /api/v10.0.0/search?location={place}&category={c}&p={page}`` -- the
  JSON:API endpoint the search page itself calls. Returns ``data[]`` of listing
  stubs plus a ``meta.total``.
* ``GET /api/v10.0.0/categories/compact`` -- the authoritative category tree.
  See ``sheypoor_taxonomy``, whose ids come from here.
* ``GET https://www.sheypoor.com/v/{slug}-{id}.html`` -- the detail *page*. There
  is no detail API (every ``/listing/{id}``-shaped path 404s), but the page
  carries a schema.org ``Offer`` JSON-LD with the area, room count, amenities,
  description and -- unlike Delta -- real coordinates.

Note that the rendered search page itself contains **no listings**: it is 700KB
of navigation and fetches its results over the API above. Scraping that HTML
would yield zero rows, which is why the client talks to the API directly.

Both templates are overridable via settings for the same reason as every other
source: a portal change should surface as a clear job error, not as a silently
empty crawl.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.logging import get_logger
from app.services.scraper.divar_client import StealthClient
from app.services.scraper.sheypoor_taxonomy import (
    SEARCH_API_PATH,
    build_search_params,
)

logger = get_logger("app.scraper.sheypoor")

#: Detail pages embed a schema.org Offer as a plain ``application/ld+json`` block.
_LD_JSON_RE = re.compile(
    r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.DOTALL
)

#: Social preview image, which on a Sheypoor detail page is the listing's own
#: first photo. This is the *only* per-listing image the site renders server-side.
_OG_IMAGE_RE = re.compile(
    r"<meta[^>]+property=[\"']og:image[\"'][^>]+content=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)

#: The listing id embedded in a CDN path: ``.../imgs/2026/10/03/467915222/...``.
_IMAGE_ID_RE = re.compile(r"/imgs/\d{4}/\d{2}/\d{2}/(\d+)/")


def image_belongs_to(url: str | None, listing_id: str) -> bool:
    """Whether a CDN URL is provably this listing's own photo.

    Sheypoor's detail page embeds twenty-plus CDN URLs, almost all of them
    belonging to *other* listings in the "similar properties" rail. Blindly
    harvesting ``/imgs/`` URLs would therefore attach a neighbour's apartment to
    this listing -- a silent data-integrity bug that is far worse than having no
    photo at all, because it looks correct on the page.

    Every Sheypoor photo path embeds its own listing id as a path segment, so the
    check is exact rather than a heuristic. A URL with no recognisable id (a
    future CDN layout, or an off-CDN image) is rejected rather than trusted.
    """
    if not url or not listing_id:
        return False
    match = _IMAGE_ID_RE.search(url)
    return bool(match) and match.group(1) == listing_id


def _iter_image_urls(node: Any) -> list[str]:
    """Flatten a schema.org ``image`` value into plain URLs.

    Accepts every shape the two blocks use: a bare string, an ``ImageObject``
    with ``contentUrl``, a list of either, or a nested ``{"thumbnails": {...}}``
    object as the search stub sends.
    """
    out: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            if value:
                out.append(value)
        elif isinstance(value, dict):
            content = value.get("contentUrl") or value.get("url")
            if isinstance(content, str) and content:
                out.append(content)
                return
            thumbnails = value.get("thumbnails")
            if isinstance(thumbnails, dict):
                for key in ("round", "square", "big", "medium", "landscape", "default"):
                    candidate = thumbnails.get(key)
                    if isinstance(candidate, str) and candidate:
                        out.append(candidate)
                        return
        elif isinstance(value, list):
            for entry in value:
                walk(entry)

    walk(node)
    return out


def extract_detail_jsonld(html: str) -> dict[str, Any]:
    """Pull the listing's structured data out of a Sheypoor detail page.

    Sheypoor ships **two different schema.org shapes** for the same listing, and
    which one a page carries is not stable -- the same category returns both:

    * ``Offer`` -- carries ``price``, ``priceCurrency``, ``category`` and an
      ``itemOffered`` with ``floorSize``/``geo``/``amenityFeature``, but **no**
      ``image`` field at all.
    * ``ItemPage`` -- carries no top-level price, but its ``mainEntity`` holds the
      **full photo gallery** as ``image[]``, plus ``floorSize``, ``geo``,
      ``description`` and a nested ``offers`` block.

    Reading whichever block came first -- which is what this used to do -- meant
    roughly half of all listings lost their gallery *and* their price, and the loss
    was invisible because the row still ingested cleanly.

    So the blocks are parsed, scored on how much listing data they actually carry,
    and the richest is normalised into the single ``Offer``-like shape the parser
    already understands. Returns ``{}`` when nothing parses, so the caller can fail
    the listing with a clear message instead of storing an empty row.
    """
    best: dict[str, Any] | None = None
    best_score = -1
    for match in _LD_JSON_RE.finditer(html or ""):
        try:
            parsed = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            # Sheypoor emits several blocks and one of them can be malformed.
            logger.debug("sheypoor: unparseable ld+json block, skipping")
            continue
        if not isinstance(parsed, dict) or not parsed.get("@type"):
            continue
        score = _ld_jsonld_richness(parsed)
        if score > best_score:
            best, best_score = parsed, score

    if best is None:
        return {}
    return _normalise_ld_json(best)


def _ld_jsonld_richness(obj: dict[str, Any]) -> int:
    """How much listing data a JSON-LD block carries, as a comparable score.

    Counts the fields the detail parser actually reads rather than trusting the
    block's position or its declared ``@type``: Sheypoor is not consistent about
    which block comes first, and the two shapes are not mutually exclusive in the
    wild (a page can carry a thin ``Offer`` plus a rich ``ItemPage``).
    """
    candidate = obj.get("mainEntity") if obj.get("@type") == "ItemPage" else None
    if not isinstance(candidate, dict):
        candidate = obj

    score = 0
    if obj.get("@type") == "Offer":
        score += 4
    if isinstance(obj.get("image"), list) or isinstance(candidate.get("image"), list):
        score += 3
    if obj.get("price") or candidate.get("price") or candidate.get("offers"):
        score += 3
    if isinstance(candidate.get("floorSize"), dict):
        score += 2
    if isinstance(candidate.get("geo"), dict):
        score += 2
    if isinstance(candidate.get("amenityFeature"), list):
        score += 1
    if obj.get("description") or candidate.get("description"):
        score += 1
    return score


def _normalise_ld_json(obj: dict[str, Any]) -> dict[str, Any]:
    """Flatten an ``ItemPage`` into the ``Offer`` shape the parser reads.

    Hoists ``mainEntity``'s fields to the top level and merges the nested
    ``offers`` block's price in. Anything already present wins, so a genuine
    ``Offer`` block passes through essentially untouched.
    """
    if obj.get("@type") != "ItemPage":
        return obj

    main = obj.get("mainEntity")
    if not isinstance(main, dict):
        return obj

    merged: dict[str, Any] = dict(obj)
    for key, value in main.items():
        if key.startswith("@") or value in (None, "", [], {}):
            continue
        merged[key] = value

    # ``ItemPage`` gives a single "address" string; the parser wants the
    # PostalAddress object the ``Offer`` shape provides.
    address = main.get("address")
    if isinstance(address, str):
        merged["address"] = address

    return merged


class SheypoorClient(StealthClient):
    """Async client for Sheypoor's public JSON:API and detail pages.

    Pacing, TLS impersonation, retries and proxy rotation are inherited from
    :class:`StealthClient`, which is what keeps a second source from quietly
    diverging on rate limiting.
    """

    #: Slug of the category the last ``search`` covered.
    #:
    #: The detail page cannot be trusted to name its own asset type: its
    #: ``itemOffered.@type`` reads "Apartment" even for a land or villa listing.
    #: The category the job searched under is the only authoritative signal, and a
    #: job runs search-then-details on one client instance, so it is cached here
    #: and stamped onto each detail payload. That keeps the shared
    #: ``parse_detail(payload, token)`` dispatch signature untouched.
    _last_search_category: str | None = None

    #: Listing id -> cover URL, harvested from the last ``search`` response.
    #:
    #: Needed because the detail JSON-LD carries **no** ``image`` field at all --
    #: its keys are only ``@context/@id/@type/url/name/description/price/
    #: priceCurrency/availability/category/itemOffered`` -- so a detail-only scrape
    #: cannot produce a gallery. The search stub, by contrast, always ships
    #: ``attributes.images.thumbnails``. Cached per token rather than per client so
    #: one listing's photo can never leak onto another when a job pages through
    #: results before fetching details.
    _search_images: dict[str, str] = {}

    #: Listing id -> labelled price parts, harvested from the last ``search``.
    #:
    #: Needed for the same reason as the images: the detail JSON-LD flattens a
    #: rent quote to a single ``price`` holding the *deposit*, so the monthly
    #: figure is only available from the search stub's ``رهن``/``اجاره`` pair.
    _search_prices: dict[str, dict[str, str]] = {}
    _search_cities: dict[str, str] = {}

    # ------------------------------------------------------------------ search
    async def search(
        self,
        city: str,
        category: str,
        page: int = 1,
        districts: list[str] | tuple[str, ...] | None = None,
    ) -> dict:
        """Fetch one page of Sheypoor search results (raw JSON:API).

        ``city`` doubles as Sheypoor's ``location`` segment, which is a city, a
        province, or ``iran`` for the whole country. ``districts`` is accepted
        because the shared pipeline passes it for every source, but Sheypoor has
        no district ids here -- it is ignored rather than silently dropping the
        narrowing, because pretending to honour it would return national results
        for a city-scoped job.
        """
        if districts:
            logger.info(
                "sheypoor: ignoring district narrowing %s (no district filter)",
                ",".join(str(d) for d in districts),
            )
        params = build_search_params(city, category, page=page)
        from app.services.scraper.sheypoor_taxonomy import resolve_slug

        resolved = resolve_slug(category)
        self._last_search_category = resolved.slug if resolved else category
        path = getattr(self.settings, "sheypoor_search_path", SEARCH_API_PATH)
        # The bare /search endpoint ignores location/category query parameters
        # and returns nationwide results. The source routes both in the path.
        from urllib.parse import quote

        url = (self.settings.sheypoor_web_base_url + path.rstrip('/') + '/'
               + quote(city.strip().lower(), safe='-') + '/'
               + quote(self._last_search_category, safe='-'))
        response = await self._request("GET", url, params={"p": params["p"]})
        payload = response.json()

        # Seed the cover-image and price caches. Id-scoped and validated,
        # because the only alternative -- re-deriving them from the detail page --
        # would mean parsing the same HTML twice, and the detail page carries
        # neither.
        from app.services.scraper.sheypoor_parser import (
            _price_parts,
            parse_sheypoor_search,
        )

        for summary in parse_sheypoor_search(payload):
            if summary.city:
                self._search_cities[summary.token] = summary.city
            if summary.image_url:
                self._search_images[summary.token] = summary.image_url
            raw_item = summary.raw if isinstance(summary.raw, dict) else None
            if raw_item is not None:
                parts = _price_parts(raw_item)
                if parts:
                    self._search_prices[summary.token] = parts

        return payload

    # ------------------------------------------------------------------ detail
    async def get_listing(self, listing_id: str) -> dict:
        """Fetch one listing's detail payload.

        Returns the normalised structured data, with the listing id, the
        canonical URL and the verified photos folded in, so the parser does not
        have to re-derive them.

        Photo sourcing, in priority order. Sheypoor publishes no gallery API
        (``/listing/{id}``, ``/listing/{id}/images`` and ``/photos/{id}`` all 404)
        and its CDN rejects size rewriting, so the page's own markup is the only
        source:

        1. the ``image[]`` array on the ``ItemPage`` block, which is the real
           gallery (verified per URL against the listing id -- the page also
           carries other listings' photos in its recommendations rail);
        2. the detail page's ``og:image`` social preview;
        3. the search stub's thumbnail for this token.

        Every URL passes :func:`image_belongs_to`, and duplicates are dropped, so
        a listing never stores the same photo twice under two renditions.
        """
        from app.services.scraper.sheypoor_taxonomy import build_detail_url

        url = build_detail_url(listing_id)
        response = await self._request("GET", url)

        payload = extract_detail_jsonld(response.text)
        if not payload:
            from app.services.scraper.divar_client import ScraperResponseError

            raise ScraperResponseError(
                f"no schema.org JSON-LD in Sheypoor response for {url}"
            )

        images: list[str] = []
        for candidate in _iter_image_urls(payload.get("image")):
            if image_belongs_to(candidate, listing_id) and candidate not in images:
                images.append(candidate)

        og_image = _OG_IMAGE_RE.search(response.text or "")
        if og_image and image_belongs_to(og_image.group(1), listing_id):
            if og_image.group(1) not in images:
                images.append(og_image.group(1))

        # Last resort: the search stub. Its thumbnails use a different size token
        # from the page's own renditions, so this is a genuine alternative rather
        # than a duplicate of a URL already collected.
        search_image = self._search_images.get(listing_id)
        if (
            search_image
            and image_belongs_to(search_image, listing_id)
            and search_image not in images
        ):
            images.append(search_image)

        payload.setdefault("__id", listing_id)
        # Preserve explicit empty/null detail values; search context remains in a
        # separate field so parser/pipeline can validate it before any fallback.
        payload["__search_city"] = self._search_cities.get(listing_id)
        payload.setdefault("__url", url)
        if images:
            payload["__images"] = images
        price_parts = self._search_prices.get(listing_id)
        if price_parts:
            payload["__price_parts"] = price_parts
        if self._last_search_category:
            payload["__category"] = self._last_search_category
        return payload

    # Alias so a Sheypoor client satisfies the same duck-typed interface the
    # ingestion pipeline uses for Divar (``get_post``).
    get_post = get_listing


__all__ = ["SheypoorClient", "extract_detail_jsonld"]