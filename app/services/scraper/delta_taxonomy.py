"""Delta.ir slug registry: cities, deal types, and property types.

Delta's routing is URL-driven -- ``/{city}/{deal}/{property-type}`` -- and it
404s on an unknown segment rather than falling back, so the node has to know the
vocabulary before it builds a URL. Divar's equivalent lives in
``app/services/scraper/cities.py`` (numeric ``city_id`` / district ids); Delta
uses human-readable slugs, so this is a plain set of strings.

Every value here was confirmed against the live site; see ``probe_delta.py`` in
the repo root for the crawl that established them.
"""

from __future__ import annotations

#: City slugs Delta serves. ``tehran`` is the default and the site's root
#: redirects to it.
DELTA_CITIES: tuple[str, ...] = (
    "tehran",
    "mashhad",
    "isfahan",
    "shiraz",
    "tabriz",
    "kermanshah",
    "urmia",
    "rasht",
)

#: Deal-type slugs. Delta nests these under the city segment.
DELTA_DEAL_TYPES: tuple[str, ...] = (
    "buy",
    "rent",
    "mortgage",
    "trade",
)

#: Property-type slugs. These name the asset, not the use, so ``office`` covers
#: both a sales office and a rented one -- the deal slug carries which.
DELTA_PROPERTY_TYPES: tuple[str, ...] = (
    "apartment",
    "villa",
    "land",
    "office",
    "store",
    "warehouse",
    "industrial",
    "garden",
)

#: Delta detail pages are addressable by five shapes. The node normalises any of
#: them down to the bare numeric listing id.
DETAIL_URL_PATTERNS: tuple[str, ...] = (
    "/detail/{listing_id}",
    "/{city}/detail/{listing_id}",
    "/{city}/{deal}/{property_type}/detail/{listing_id}",
    "/listing/{listing_id}",
    "/{listing_id}",
)


def normalise_city(slug: str) -> str:
    """Validate a city slug, returning it lower-cased.

    Raises ``ValueError`` on anything not in :data:`DELTA_CITIES` so a typo
    surfaces as a clear job error instead of a silent zero-listing result.
    """
    value = (slug or "").strip().lower()
    if value not in DELTA_CITIES:
        raise ValueError(
            f"{slug!r} is not a known Delta city; expected one of "
            f"{', '.join(DELTA_CITIES)}"
        )
    return value


def normalise_deal_type(slug: str) -> str:
    """Validate a deal-type slug, returning it lower-cased."""
    value = (slug or "").strip().lower()
    if value not in DELTA_DEAL_TYPES:
        raise ValueError(
            f"{slug!r} is not a known Delta deal type; expected one of "
            f"{', '.join(DELTA_DEAL_TYPES)}"
        )
    return value


def normalise_property_type(slug: str) -> str:
    """Validate a property-type slug, returning it lower-cased."""
    value = (slug or "").strip().lower()
    if value not in DELTA_PROPERTY_TYPES:
        raise ValueError(
            f"{slug!r} is not a known Delta property type; expected one of "
            f"{', '.join(DELTA_PROPERTY_TYPES)}"
        )
    return value


def listing_id_from_url(url: str) -> str | None:
    """Extract the numeric listing id from any of Delta's detail URL shapes.

    Returns ``None`` for a URL that is not a Delta detail page, so a crawler
    following an off-site link skips it instead of creating a junk listing.
    """
    from urllib.parse import urlparse

    path = urlparse((url or "").strip()).path
    if not path:
        return None
    segments = [part for part in path.split("/") if part]
    if "detail" in segments:
        index = segments.index("detail")
        if index + 1 < len(segments):
            return segments[index + 1]
        return None
    # Bare ``/listing/{id}`` and ``/{id}`` shapes.
    for segment in reversed(segments):
        if segment.isdigit():
            return segment
    return None


__all__ = [
    "DELTA_CITIES",
    "DELTA_DEAL_TYPES",
    "DELTA_PROPERTY_TYPES",
    "DETAIL_URL_PATTERNS",
    "listing_id_from_url",
    "normalise_city",
    "normalise_deal_type",
    "normalise_property_type",
]