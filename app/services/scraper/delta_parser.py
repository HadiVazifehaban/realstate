"""Map a Delta listing's schema.org payload onto the unified listing schema.

Delta's detail pages expose one ``schema.org/Product`` object. This module turns
it into the same :class:`DivarListingDetail` (aliased ``UnifiedListingDetail``)
that every other source emits, so the ingestion pipeline never needs to know
which portal a row came from.

Three Delta quirks are handled here and nowhere else:

* **The currency label lies.** Delta reports ``priceCurrency: "IRR"`` but the
  figure is toman -- ``139 m²`` at ``53,000,000,000`` is ~381 m toman/m², which
  matches the listing's own ``قیمت متری`` field exactly. Treating it as rial
  would overstate every price by 10x.
* **Specs live in ``amenityFeature``, not named fields.** Area, floor, year and
  the amenity booleans all arrive as ``{"name": <Persian label>, "value": ...}``
  rows, so they are read through a label map rather than field lookups.
* **No coordinates, no description, no date.** Delta does not put them in the
  JSON-LD. Rather than invent them, they are left unset: the sanitiser resolves
  the pin by reverse geocoding the neighbourhood, and the description stays empty
  until a source that carries one is read.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.models.enums import DealType, PropertyType
from app.services.scraper.parser import (
    DivarListingDetail,
    DivarListingSummary,
    map_category,
    normalize_digits,
    parse_int,
    parse_price,
)

logger = get_logger("app.scraper.delta_parser")

#: Delta's own slug for each asset type, keyed by the unified enum. Reversed so
#: the job's Divar-style category slug can be mapped back onto Delta's routing.
DELTA_PROPERTY_TYPE_BY_SLUG: dict[str, PropertyType] = {
    "apartment": PropertyType.APARTMENT,
    "villa": PropertyType.VILLA,
    "land": PropertyType.LAND,
    "office": PropertyType.OFFICE,
    "store": PropertyType.STORE,
    "warehouse": PropertyType.WAREHOUSE,
    "industrial": PropertyType.INDUSTRIAL,
    "garden": PropertyType.GARDEN,
}

#: Delta's deal segment -> unified enum.
DELTA_DEAL_TYPE_BY_SLUG: dict[str, DealType] = {
    "buy": DealType.SALE,
    "rent": DealType.RENT,
    "mortgage": DealType.FULL_MORTGAGE,
    # A swap listing has no equivalent in the unified schema; it ingests as a
    # sale so the row is still searchable rather than dropped.
    "trade": DealType.SALE,
}

#: Persian amenity label -> unified boolean field.
_TRUE_FLAGS: dict[str, str] = {
    "پارکینگ": "has_parking",
    "آسانسور": "has_elevator",
    "انباری": "has_storage",
    "بالکن": "has_balcony",
}

#: The label Delta uses for the sale price per square metre.
PRICE_PER_METER_LABEL = "قیمت متری"


def _amenity_map(item: dict) -> dict[str, str]:
    """Collapse ``amenityFeature`` rows into ``{Persian label: value}``."""
    out: dict[str, str] = {}
    for entry in item.get("amenityFeature") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if name:
            out[name] = str(entry.get("value") or "").strip()
    return out


def _is_true(value: str) -> bool | None:
    """Read a Delta boolean flag.

    Delta sends ``"true"``/``"false"`` but localises the surrounding markup, so
    Persian/Arabic spellings are accepted too. Anything unrecognised returns
    ``None`` -- unknown, not false -- so a layout change cannot silently flip an
    amenity to "missing".
    """
    normalised = normalize_digits(value or "").strip().lower()
    if normalised in ("true", "1", "بله", "دارد", "yes", "دارای"):
        return True
    if normalised in ("false", "0", "خیر", "ندارد", "no"):
        return False
    return None


def _years_built_from_age(value: str) -> int | None:
    """Turn Delta's ``"‫19 ساله‬"`` age into a build year.

    Delta reports the *age* of the building, not a year. Anchored to the current
    Persian year because that is the calendar a reader of the listing is in.
    Returns ``None`` when the age is missing or implausible rather than guessing.
    """
    age = parse_int(value)
    if age is None or not 0 <= age <= 120:
        return None
    return 1404 - age


def parse_delta_detail(
    payload: dict,
    token: str,
    *,
    phone: str | None = None,
) -> DivarListingDetail:
    """Map one Delta ``Product`` payload onto the unified listing schema."""
    item = payload.get("item") or {}
    offers = payload.get("offers") or {}
    amenities = _amenity_map(item)
    url = str(payload.get("url") or payload.get("__url") or "")

    property_type, deal_type = _types_from_url(url, payload.get("__context"))

    # Delta JSON-LD may include its city in a typed address or explicit field.
    # Never promote request context here: the pipeline can only use it after
    # resolving and matching the detail city to the curated city catalog.
    address = payload.get("address") or item.get("address") or {}
    if not isinstance(address, dict):
        address = {}
    raw_city = payload.get("city") or payload.get("cityName") or address.get("addressLocality")
    raw_province = payload.get("province") or address.get("addressRegion")
    from app.services.location_catalog import resolve_city

    located_city = resolve_city(str(raw_city or "").strip(), str(raw_province or "").strip()) if str(raw_city or "").strip() else None

    # Area: the amenity row is authoritative, but Delta omits it on some rows and
    # then leads ``item.name`` with the area ("139 متر / فول / اقدسیه").
    area = parse_int(amenities.get("مساحت ملک"))
    if area is None:
        area = parse_int(item.get("name"))

    price_per_meter = None
    additional = offers.get("additionalProperty") or {}
    if isinstance(additional, dict) and additional.get("name") == PRICE_PER_METER_LABEL:
        price_per_meter = parse_price(additional.get("value"))

    flags: dict[str, bool | None] = {}
    for label, field in _TRUE_FLAGS.items():
        if label in amenities:
            flags[field] = _is_true(amenities[label])

    agent = payload.get("offeredBy") or {}
    agency = payload.get("realEstateAgency") or {}

    images = [str(url) for url in (payload.get("image") or []) if isinstance(url, str)]

    return DivarListingDetail(
        token=str(token),
        title=str(payload.get("title") or payload.get("name") or item.get("name") or ""),
        # Delta keeps the long description out of the JSON-LD.
        description="",
        city=located_city["name"] if located_city else "",
        province=located_city["province"] if located_city else "",
        district=str(raw_province or ""),
        neighborhood="",
        category=property_type.value.lower() if property_type else "",
        property_type=property_type,
        deal_type=deal_type,
        # Toman despite the "IRR" label; see the module docstring.
        total_price=parse_price(offers.get("price")),
        deposit=None,
        monthly_rent=None,
        price_per_meter=price_per_meter,
        price_is_convertible=None,
        area=area,
        land_area=None,
        rooms=parse_int(item.get("numberOfRooms")) or parse_int(amenities.get("تعداد اتاق")),
        year_built=_years_built_from_age(amenities.get("عمر تقریبی بنا", "")),
        floor=parse_int(item.get("floorLevel")) or parse_int(amenities.get("طبقه")),
        total_floors=parse_int(amenities.get("تعداد طبقات")),
        units_per_floor=None,
        has_elevator=flags.get("has_elevator"),
        has_parking=flags.get("has_parking"),
        has_storage=flags.get("has_storage"),
        has_balcony=flags.get("has_balcony"),
        latitude=None,
        longitude=None,
        # Delta pins exactly, with no fuzzing of its own.
        coordinate_radius=None,
        images=images,
        phone=phone,
business_type="AGENCY" if agency.get("name") else "PERSONAL",
        agent_name=str(agent.get("name")) if agent.get("name") else None,
        agent_slug=_slug_from_url(agent.get("url")),
        agency_name=str(agency.get("name")) if agency.get("name") else None,
        agency_slug=_slug_from_url(agency.get("url")),
        raw=payload,
    )


def _slug_from_url(value: Any) -> str | None:
    """Take the last path segment of an ``offeredBy``/agency URL."""
    if not value:
        return None
    return str(value).rstrip("/").rsplit("/", 1)[-1] or None


def _types_from_url(url: str, context: dict | None = None) -> tuple[PropertyType | None, DealType | None]:
    """Recover the property and deal type for a Delta listing.

    Detail pages sit at ``/{city}/{deal}/{type}/detail/{id}`` for some listings
    and at the canonical ``/detail/{id}`` for most, which carries no type segment
    at all. The URL is tried first; when it says nothing, the search context the
    client stamped on the payload is used, so a listing found under
    ``/tehran/rent/apartment`` still ingests as a rented apartment rather than an
    untyped row.
    """
    from app.services.scraper.delta_taxonomy import listing_id_from_url

    path = str(url or "")
    segments = [part for part in path.split("/") if part]
    if "detail" in segments:
        head = segments[: segments.index("detail")]
        # Drop a leading numeric listing id from the ``/{id}`` shape.
        head = [part for part in head if not part.isdigit()]
        deal = next(
            (DELTA_DEAL_TYPE_BY_SLUG[part] for part in head if part in DELTA_DEAL_TYPE_BY_SLUG),
            None,
        )
        prop = next(
            (
                DELTA_PROPERTY_TYPE_BY_SLUG[part]
                for part in head
                if part in DELTA_PROPERTY_TYPE_BY_SLUG
            ),
            None,
        )
        if deal or prop:
            return prop, deal

    context = context or {}
    return (
        DELTA_PROPERTY_TYPE_BY_SLUG.get(str(context.get("property_type") or "")),
        DELTA_DEAL_TYPE_BY_SLUG.get(str(context.get("deal") or "")),
    )


def parse_delta_search(payload: dict) -> list[DivarListingSummary]:
    """Turn a Delta list page into listing summaries.

    Delta's list pages carry no structured data -- only links to detail pages --
    so a summary carries the id and the URL it came from, and the pipeline fetches
    the detail page to fill in the rest. Titles and prices are therefore empty on
    this pass by design, not by failure.
    """
    from app.services.scraper.delta_client import extract_listing_ids

    ids = payload.get("listing_ids") or []
    if isinstance(ids, str):
        ids = [ids]
    base = str(payload.get("url") or "")
    detail_template = "/detail/{listing_id}"
    return [
        DivarListingSummary(
            token=str(listing_id),
            title="",
            city=str(payload.get('city') or '') if isinstance(payload, dict) else '',
            district="",
            category="",
            price_hint="",
            image_url=None,
            raw={"listing_id": listing_id, "list_url": base, "detail_url": detail_template.format(listing_id=listing_id)},
        )
        for listing_id in ids
    ]


__all__ = [
    "DELTA_DEAL_TYPE_BY_SLUG",
    "DELTA_PROPERTY_TYPE_BY_SLUG",
    "map_category",
    "parse_delta_detail",
    "parse_delta_search",
]