"""Sheypoor category registry: the ``c=`` ids and URL slugs for real estate.

Sheypoor routes real-estate browsing by a **category id** carried in the query
string (``?c=43608``) and by a **human-readable slug** in the path
(``/s/iran/plots-land``). Both are needed: the slug builds the URL, the id is
what the page actually filters on. The node has to know the vocabulary before it
can build a request, because an unknown ``c=`` returns 200 with an unrelated
listing set rather than an error.

PROVENANCE
----------
Every id and slug below was read out of Sheypoor's own category API,
``GET /api/v10.0.0/categories/compact`` (the real-estate node is ``c=43603``),
on 2026-10-05. That matters: an earlier pass took these values from the
real-estate menu and got most of them wrong -- ``land`` is ``44099``, not
43608; ``house-apartment-for-rent`` is ``43606``, not 43605; and
``presale-properties`` does not exist at all (it is ``real-estate-services``,
``c=45001``). An unknown ``c=`` does not error -- it silently returns a different
inventory -- so these are pinned to the API rather than to a hand transcription.

MAPPINGS THAT ARE LOSSY, DELIBERATELY
--------------------------------------
The unified schema has no member for two Sheypoor deal types:

* ``real-estate-short-term-rental`` (short-stay / بوم‌گردی) has no short-let
  concept. It is ingested as ``RENT`` so it stays searchable.
* ``real-estate-services`` (پیش‌فروش و مشارکت) has no ``PRE_SALE`` member -- the
  enum's third value is ``FULL_MORTGAGE``. It is ingested as ``SALE``.

The three ``commercial-properties-*`` slugs cover shops, offices, warehouses and
industrial units alike. The sub-type is only in the listing body, so it is left
unset rather than guessed: a mis-typed shop is worse than an untyped row a human
can correct.
"""

from __future__ import annotations

from app.models.enums import DealType, PropertyType

#: Root real-estate category; every sub-category below hangs off it.
ROOT_CATEGORY_ID = 43603


class SheypoorCategory:
    """One row of Sheypoor's real-estate menu."""

    __slots__ = ("slug", "category_id", "property_type", "deal_type", "label")

    def __init__(
        self,
        slug: str,
        category_id: int | None,
        property_type: PropertyType | None,
        deal_type: DealType | None,
        label: str,
    ) -> None:
        self.slug = slug
        self.category_id = category_id
        self.property_type = property_type
        self.deal_type = deal_type
        self.label = label

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"SheypoorCategory({self.slug!r}, c={self.category_id})"


#: Ordered as Sheypoor presents them. Ids and slugs are the API's, not a
#: hand-transcription -- see the module docstring for what that costs when wrong.
SHEYPOOR_CATEGORIES: tuple[SheypoorCategory, ...] = (
    SheypoorCategory(
        "houses-apartments-for-sale", 43604, PropertyType.APARTMENT, DealType.SALE,
        "خرید و فروش خانه و آپارتمان",
    ),
    SheypoorCategory(
        "house-apartment-for-rent", 43606, PropertyType.APARTMENT, DealType.RENT,
        "رهن و اجاره خانه و آپارتمان",
    ),
    SheypoorCategory(
        "villa-for-sale", 44586, PropertyType.VILLA, DealType.SALE,
        "خرید و فروش ویلا",
    ),
    SheypoorCategory(
        # No short-let member in the unified schema; ingested as RENT.
        "real-estate-short-term-rental", 44585, None, DealType.RENT,
        "اجاره کوتاه مدت ویلا، سوئیت",
    ),
    SheypoorCategory(
        "land", 44099, PropertyType.LAND, DealType.SALE,
        "زمین و باغ",
    ),
    SheypoorCategory(
        # Sub-type (shop/office/warehouse) is only in the listing body.
        "commercial-properties-for-sale", 43605, None, DealType.SALE,
        "خرید و فروش اداری، تجاری و صنعتی",
    ),
    SheypoorCategory(
        "commercial-properties-for-rent", 43607, None, DealType.RENT,
        "رهن و اجاره اداری، تجاری و صنعتی",
    ),
    SheypoorCategory(
        # No PRE_SALE member in the unified schema; ingested as SALE.
        "real-estate-services", 45001, PropertyType.APARTMENT, DealType.SALE,
        "پیش فروش و مشارکت در ساخت",
    ),
    SheypoorCategory(
        "other-real-estate", 44115, None, None,
        "سایر املاک",
    ),
)

BY_SLUG: dict[str, SheypoorCategory] = {c.slug: c for c in SHEYPOOR_CATEGORIES}
BY_ID: dict[int, SheypoorCategory] = {
    c.category_id: c for c in SHEYPOOR_CATEGORIES if c.category_id is not None
}

#: Detail URLs end ``-{id}.html``; the id is what the node keys listings on.
DETAIL_ID_RE = r"-(\d+)\.html$"

#: Sheypoor's real JSON API. Verified 2026-10-05: this is the endpoint the search
#: page itself calls, and the earlier ``/api/web/v1/...`` guess 404s.
SEARCH_API_PATH = "/api/v10.0.0/search"
CATEGORIES_API_PATH = "/api/v10.0.0/categories/compact"

#: ``location`` is the place segment Sheypoor uses in its own URLs -- a city
#: ("tehran"), a province ("fars"), or the country ("iran") for everything.
LIST_URL_TEMPLATE = "https://www.sheypoor.com/s/{location}/{slug}?c={category_id}"
DETAIL_URL_TEMPLATE = "https://www.sheypoor.com/v/{slug}-{listing_id}.html"


def resolve_slug(slug: str) -> SheypoorCategory | None:
    """Look a category up by slug, tolerating case and stray whitespace."""
    return BY_SLUG.get((slug or "").strip().lower())


def resolve_category_id(value: object) -> SheypoorCategory | None:
    """Look a category up by its ``c=`` id, which may arrive as a string."""
    if value is None:
        return None
    try:
        return BY_ID.get(int(str(value).strip()))
    except (TypeError, ValueError):
        return None


def map_category_to_types(slug: str) -> tuple[PropertyType | None, DealType | None]:
    """Map a Sheypoor category slug onto the unified (property, deal) pair.

    Returns ``(None, None)`` for an unknown slug. Callers fall back to the generic
    :func:`app.services.scraper.parser.map_category` heuristic rather than
    dropping the listing.
    """
    category = resolve_slug(slug)
    if category is None:
        return None, None
    return category.property_type, category.deal_type


def build_list_url(
    location_slug: str, category_slug: str, *, page: int = 1
) -> str:
    """Build the human-facing Sheypoor real-estate URL for a category.

    This is the *page* a broker would open, not what the crawler requests -- the
    crawler calls :data:`SEARCH_API_PATH` instead, because the page renders its
    listings client-side and its HTML contains none.

    Raises ``ValueError`` on an unknown category so the job fails with a clear
    message instead of crawling an unrelated listing set.
    """
    category = resolve_slug(category_slug)
    if category is None or category.category_id is None:
        raise ValueError(
            f"{category_slug!r} is not a known Sheypoor real-estate category slug"
        )
    url = LIST_URL_TEMPLATE.format(
        location=(location_slug or "").strip().lower(),
        slug=category.slug,
        category_id=category.category_id,
    )
    return f"{url}&p={page}" if page > 1 else url


def build_search_params(
    location_slug: str, category_slug: str, *, page: int = 1
) -> dict[str, str]:
    """Query parameters for :data:`SEARCH_API_PATH`.

    ``p`` is 1-based, matching the page URL's own pagination.
    """
    category = resolve_slug(category_slug)
    if category is None or category.category_id is None:
        raise ValueError(
            f"{category_slug!r} is not a known Sheypoor real-estate category slug"
        )
    return {
        "location": (location_slug or "").strip().lower(),
        "category": str(category.category_id),
        "p": str(max(page, 1)),
    }


def build_detail_url(listing_id: str, *, title_slug: str = "listing") -> str:
    """Build a Sheypoor detail URL for a numeric listing id.

    The slug segment is cosmetic -- Sheypoor routes on the trailing id -- so a
    stable placeholder is used rather than transliterating a Persian title, which
    would need a transliteration table that buys nothing.
    """
    return DETAIL_URL_TEMPLATE.format(
        slug=title_slug.strip() or "listing", listing_id=listing_id
    )


__all__ = [
    "BY_ID",
    "BY_SLUG",
    "CATEGORIES_API_PATH",
    "DETAIL_ID_RE",
    "ROOT_CATEGORY_ID",
    "SEARCH_API_PATH",
    "SHEYPOOR_CATEGORIES",
    "SheypoorCategory",
    "build_detail_url",
    "build_list_url",
    "build_search_params",
    "map_category_to_types",
    "resolve_category_id",
    "resolve_slug",
]