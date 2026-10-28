"""Tolerant parser for Sheypoor's structured listing JSON.

Sheypoor returns a flat, well-typed JSON shape (no widget tree like Divar), but
field names are localised and differ between the search and detail payloads. The
parser reads through a small alias table rather than a fixed path, and
normalises Persian/Arabic digits via the Divar helpers.

Output reuses the ``DivarListingSummary`` / ``DivarListingDetail`` models
deliberately: they are the project's unified listing schema, so the
deduplicator, sanitiser and PostGIS writer work for this source unchanged. Only
``PropertySource`` differs, and the pipeline passes that in explicitly.
"""

from __future__ import annotations

from typing import Any, Iterator

from app.models.enums import DealType
from app.services.scraper.parser import (
    DivarListingDetail,
    DivarListingSummary,
    map_category,
    parse_bool,
    parse_float,
    parse_int,
    parse_price,
)
from app.services.scraper.sheypoor_taxonomy import map_category_to_types


def _first(item: dict[str, Any], *names: str) -> Any:
    """Return the first present, non-empty alias from ``names``."""
    for name in names:
        if name in item and item[name] not in (None, ""):
            return item[name]
    return None


def _walk(node: Any, key: str) -> Any:
    """Depth-first search for ``key`` anywhere in a nested structure."""
    if isinstance(node, dict):
        if key in node and node[key] not in (None, ""):
            return node[key]
        for value in node.values():
            found = _walk(value, key)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _walk(value, key)
            if found is not None:
                return found
    return None


#: Sheypoor joins place names with an Arabic comma in its own UI.
_PLACE_SEPARATOR = "،"


def _leading_place(value: Any) -> str:
    """City half of Sheypoor's ``"تهران، آهنگ"`` location string."""
    text = str(value or "").split(_PLACE_SEPARATOR)[0].strip()
    return text


def _trailing_place(value: Any) -> str:
    """Locality half of Sheypoor's ``"تهران، آهنگ"`` location string."""
    parts = [part.strip() for part in str(value or "").split(_PLACE_SEPARATOR)]
    return parts[1] if len(parts) > 1 else ""


def _attrs(item: dict[str, Any]) -> dict[str, Any]:
    """Unwrap a JSON:API resource to its ``attributes`` bag.

    Sheypoor's search endpoint returns ``{"type": ..., "id": ...,
    "attributes": {...}}`` per row, while the detail JSON-LD is flat. Falling
    back to the row itself keeps every call site working against both shapes.
    """
    attributes = item.get("attributes")
    return attributes if isinstance(attributes, dict) else item


def _iter_items(payload: Any) -> Iterator[dict]:
    """Yield listing dicts from a search response, whatever envelope it uses.

    Handles the JSON:API shape (``data`` is a list of resources) as well as the
    flatter ``{items|listings|results: [...]}`` envelopes.
    """
    node = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(node, list):
        items = []
        for entry in node:
            if not isinstance(entry, dict):
                continue
            # City-scoped search groups special/normal results into sections.
            if isinstance(entry.get("items"), list):
                items.extend(i for i in entry["items"] if isinstance(i, dict))
            else:
                items.append(entry)
        return iter(items)
    for candidate in (payload, node):
        if not isinstance(candidate, dict):
            continue
        for key in ("items", "listings", "results"):
            value = candidate.get(key)
            if isinstance(value, list):
                return iter([i for i in value if isinstance(i, dict)])
    return iter(())


#: Sheypoor labels the parts of a price rather than keying them. A rent listing
#: sends two entries, a sale listing sends one unlabelled entry.
_DEPOSIT_LABELS = frozenset({"رهن", "ودیعه", "رهن و اجاره", "ودیعه و اجاره"})
_MONTHLY_LABELS = frozenset({"اجاره", "اجاره ماهانه", "اجاره ماهیانه", "کرایه"})
_PER_METER_LABELS = frozenset({"قیمت هر متر", "قیمت متری", "متری", "هر متر"})
_TOTAL_LABELS = frozenset({"قیمت", "قیمت کل", "مبلغ", "total"})


def _price_parts(item: dict[str, Any]) -> dict[str, str]:
    """Split Sheypoor's labelled ``price`` array into its components.

    Returns whichever of ``total``, ``deposit``, ``monthly`` and ``per_meter``
    the payload actually labelled, as raw display text.

    This split is the whole reason the array needs reading rather than joining.
    A rent listing arrives as::

        [{"label": "رهن",   "amount": "200,000,000"},
         {"label": "اجاره", "amount": "37,000,000"}]

    Concatenating that into one string yields a number that is neither the
    deposit nor the rent -- it is worse than blank, because it looks like a real
    asking price and would be stored as one.
    """
    raw = _first(_attrs(item), "price", "price_hint")
    if isinstance(raw, (str, int, float)):
        return {"total": str(raw)}
    if not isinstance(raw, list):
        return {}

    parts: dict[str, str] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        amount = str(entry.get("amount") or "").strip()
        if not amount:
            continue
        label = str(entry.get("label") or "").strip()
        if label in _DEPOSIT_LABELS:
            parts.setdefault("deposit", amount)
        elif label in _MONTHLY_LABELS:
            parts.setdefault("monthly", amount)
        elif label in _PER_METER_LABELS:
            parts.setdefault("per_meter", amount)
        elif label in _TOTAL_LABELS or not label:
            # An unlabelled entry is the headline figure, so it must not
            # overwrite an explicitly labelled total.
            parts.setdefault("total", amount)
        else:
            parts.setdefault("total", amount)
    return parts


def _price_amount(item: dict[str, Any]) -> str:
    """Asking price as display text, for the card's price hint.

    Prefers the headline figure; falls back to the deposit because on a rent
    listing that is the number the portal itself leads with. A negotiable asking
    price is preserved verbatim so :func:`parse_price` can recognise the
    ``"توافقی"`` marker and leave ``total_price`` unset instead of guessing zero.
    """
    parts = _price_parts(item)
    return parts.get("total") or parts.get("deposit") or ""


def _thumbnail(item: dict[str, Any]) -> str | None:
    """First thumbnail URL from Sheypoor's nested ``images`` object."""
    raw = _first(_attrs(item), "image", "image_url", "thumbnail", "images")
    if isinstance(raw, dict):
        thumbnails = raw.get("thumbnails")
        if isinstance(thumbnails, dict):
            for key in ("round", "square", "big", "medium", "default"):
                value = thumbnails.get(key)
                if isinstance(value, str) and value:
                    return value
        return None
    return str(raw) if raw else None


def _item_id(item: dict[str, Any]) -> str:
    """The stable listing id, used as the dedupe ``external_id``."""
    raw = _first(item, "id", "listing_id", "listingId", "post_id", "token")
    return str(raw) if raw is not None else ""


def parse_sheypoor_search(payload: dict) -> list[DivarListingSummary]:
    """Extract listing summaries from a Sheypoor search response."""
    from app.services.city_normalizer import is_known_city

    summaries: list[DivarListingSummary] = []
    seen: set[str] = set()
    for item in _iter_items(payload):
        token = _item_id(item)
        if not token or token in seen:
            continue
        seen.add(token)
        attributes = _attrs(item)
        # Sheypoor sends one comma-joined "location" string ("تهران، آهنگ"). A
        # flat payload instead has dedicated city/neighborhood keys, so only the
        # joined form is split -- splitting a plain neighborhood name would drop it.
        #
        # City Gate guard: some rows carry only a neighbourhood ("پونک") or a
        # phase ("فاز ۱") with no city half at all. A non-city leading half is
        # not a city -- keep it as the district so the row is not orphaned from
        # every city filter.
        location = _first(attributes, "location")
        if location:
            leading, district = _leading_place(location), _trailing_place(location)
            if is_known_city(leading):
                city = leading
            else:
                city = ""
                district = district or leading
        else:
            city = str(_first(attributes, "city", "city_slug") or "")
            district = str(
                _first(attributes, "neighborhood", "district", "locality") or ""
            )
            if city and not is_known_city(city):
                district = district or city
                city = ""
        summaries.append(
            DivarListingSummary(
                token=token,
                title=str(_first(attributes, "title", "subject") or ""),
                city=city,
                district=district,
                category=str(_first(attributes, "categoryId", "category") or ""),
                price_hint=_price_amount(item),
                image_url=_thumbnail(item),
                top_description_text=str(
                    _first(attributes, "description", "excerpt") or ""
                ),
                raw=item,
            )
        )
    return summaries


def _get(payload: dict, *names: str) -> Any:
    """Read a field from the top level, falling back to a deep search."""
    direct = _first(payload, *names)
    if direct is not None:
        return direct
    for name in names:
        found = _walk(payload, name)
        if found is not None:
            return found
    return None


def _to_float(value: Any) -> float | None:
    """Coordinates arrive as numeric strings; reject empty/non-numeric."""
    if value is None or value == "":
        return None
    return parse_float(value)


def _image_list(payload: dict) -> list[str]:
    """Collect this listing's own image URLs, in priority order.

    ``__images`` is what :meth:`SheypoorClient.get_listing` stamps on the payload:
    the detail JSON-LD has **no** ``image`` key of its own, so without it a
    Sheypoor listing is stored with zero photos and renders as an empty plate.

    The remaining keys cover the flatter fixtures the older tests use, plus a
    bare string under any of the usual names. Order is preserved and duplicates
    are dropped, because the caller stores the first entry as the cover.
    """
    candidates: list[Any] = []

    stamped = _first(payload, "__images")
    if isinstance(stamped, list):
        candidates.extend(stamped)
    elif isinstance(stamped, str) and stamped:
        candidates.append(stamped)

    raw = _first(payload, "images", "image_urls", "gallery")
    if isinstance(raw, list):
        candidates.extend(raw)
    elif isinstance(raw, dict):
        # Nested ``{"thumbnails": {...}}`` shape, as used by the search stub.
        candidates.append(raw)

    candidates.append(_first(payload, "image", "image_url", "thumbnail"))

    # A nested object may itself carry the URL one level down.
    flat: list[str] = []
    for candidate in candidates:
        if isinstance(candidate, str) and candidate:
            flat.append(candidate)
            continue
        if isinstance(candidate, dict):
            thumbnails = candidate.get("thumbnails")
            source = thumbnails if isinstance(thumbnails, dict) else candidate
            for key in ("round", "square", "big", "medium", "landscape", "default"):
                value = source.get(key)
                if isinstance(value, str) and value:
                    flat.append(value)
                    break

    seen: set[str] = set()
    return [url for url in flat if not (url in seen or seen.add(url))]
#: Sheypoor's detail JSON-LD names its amenities in English, unlike the Persian
#: labels on the page body.
_AMENITY_FLAGS: dict[str, str] = {
    "parking": "has_parking",
    "storage": "has_storage",
    "elevator": "has_elevator",
    "balcony": "has_balcony",
}


def _amenity_flags(item_offered: dict[str, Any]) -> dict[str, bool | None]:
    """Read the boolean amenity rows out of ``itemOffered.amenityFeature``."""
    out: dict[str, bool | None] = {}
    for entry in item_offered.get("amenityFeature") or []:
        if not isinstance(entry, dict):
            continue
        field = _AMENITY_FLAGS.get(str(entry.get("name") or "").strip().lower())
        if field:
            out[field] = parse_bool(entry.get("value"))
    return out


def _total_price_in_toman(payload: dict, price_parts: dict[str, str]) -> int | None:
    """The asking price, but only from a source that declares its own unit.

    Sheypoor's two JSON-LD shapes disagree about the currency of the *same*
    figure, which makes the raw number unsafe to store on its own:

    * the ``Offer`` block sends ``priceCurrency: "toman"``;
    * the ``ItemPage`` block's nested ``offers`` sends ``priceCurrency: "IRR"``
      and a value exactly **ten times** the portal's own displayed figure --
      i.e. Rial. Read as Toman it inflates every such listing 10x (an 80 m2 flat
      quoted at 7,550,000,000 becomes 94M Toman/m2, which no Tehran street
      produces).

    So a figure is accepted only when it carries an explicit تومان declaration:
    either the JSON-LD currency string, or the search stub, which labels its
    currency per entry. Anything else is dropped rather than converted --
    a missing price renders as "ثبت نشده", while a wrong one is acted on.
    """
    currency = str(_get(payload, "priceCurrency", "price_currency") or "").strip().lower()
    # An absent label is not a conflicting one: only reject when the payload
    # actively declares a different unit.
    if currency in ("", "toman", "تومان", "irr_toman"):
        parsed = parse_price(_get(payload, "price", "total_price"))
        if parsed is not None:
            return parsed

    # Search stub: the portal renders this figure itself, labelled تومان.
    return parse_price(price_parts.get("total"))


def parse_sheypoor_detail(
    payload: dict,
    token: str,
    *,
    phone: str | None = None,
) -> DivarListingDetail:
    """Map a Sheypoor detail payload onto the unified listing schema.

    Handles both shapes: the schema.org ``Offer`` the detail page actually ships
    (whose interesting fields live under ``itemOffered``) and the flatter payloads
    the older fixtures use.
    """
    item = payload.get("itemOffered") if isinstance(payload, dict) else None
    if not isinstance(item, dict):
        item = {}
    flags = _amenity_flags(item)
    address = item.get("address") if isinstance(item.get("address"), dict) else {}
    geo = item.get("geo") if isinstance(item.get("geo"), dict) else {}

    # The Offer's own ``category`` names the *deal* side only ("forSale"). A
    # combined search route is not evidence of a specific asset type; use only a
    # concrete detail-owned type/category, otherwise preserve unknown as None.
    offer_category = str(_get(payload, "category") or "")
    asset_slug = str(_get(payload, "__category") or "")
    _, deal_type = map_category_to_types(asset_slug)
    # Taxonomy entries can be route-level defaults, including specific-looking
    # types which still do not identify the individual listing. Never infer the
    # asset from crawler search context; detail-owned evidence is checked below.
    property_type = None
    for candidate in (
        _get(item, "propertyType", "property_type", "realEstateType"),
        _get(payload, "propertyType", "property_type", "realEstateType"),
    ):
        if candidate:
            actual_type, _ = map_category(str(candidate))
            if actual_type is not None:
                property_type = actual_type
                break
    if deal_type is None:
        deal_type = _deal_from_offer_category(offer_category)
    if not asset_slug and property_type is None and offer_category:
        # In legacy flat payloads ``category`` is the detail's specific category.
        # The Offer ``category`` is only a deal label and is safely unclassified.
        detail_type, detail_deal = map_category(offer_category)
        if detail_type is not None:
            property_type = detail_type
        if deal_type is None and detail_deal is not None:
            deal_type = detail_deal
    category = asset_slug or offer_category

    floor_size = item.get("floorSize") if isinstance(item.get("floorSize"), dict) else {}

    # The detail JSON-LD flattens a rent quote to one ``price`` (the deposit),
    # so the labelled split only survives in ``__price_parts``, which the client
    # caches from the search stub. Without it a rent listing loses its monthly
    # figure and the card shows a deposit as if it were the total.
    price_parts = _get(payload, "__price_parts")
    if not isinstance(price_parts, dict):
        price_parts = {}

    total_price = _total_price_in_toman(payload, price_parts)

    # City Gate guard: addressLocality is a locality, not necessarily a city --
    # it lands in BOTH slots below by design, and the shared sanitiser guard
    # (normalize_city_neighborhood) demotes non-cities to neighborhood. The
    # explicit city key wins when present, matching the search parser's rule.
    from app.services.city_normalizer import is_known_city

    location = payload.get("attributes", {}).get("location") if isinstance(payload.get("attributes"), dict) else None
    if not isinstance(location, dict):
        location = payload.get("location") if isinstance(payload.get("location"), dict) else {}
    explicit_city_value = _get(payload, "city", "city_slug")
    explicit_city = str(explicit_city_value or "").strip()
    location_city = str(_get(location, "city", "city_name", "city_slug") or "").strip()
    locality = str(address.get("addressLocality") or "").strip()
    detail_city = next(
        (candidate for candidate in (explicit_city, location_city, locality) if candidate and is_known_city(candidate)),
        "",
    )
    detail_province = str(
        _get(payload, "province", "province_name")
        or _get(location, "province", "province_name")
        or address.get("addressRegion")
        or ""
    ).strip()
    from app.services.location_catalog import resolve_city

    located = resolve_city(detail_city, detail_province) if detail_city else None
    if located:
        detail_city, detail_province = located["name"], located["province"]
    else:
        detail_city, detail_province = "", ""

    return DivarListingDetail(
        token=token,
        title=str(_get(payload, "name", "title", "subject") or ""),
        description=str(_get(payload, "description", "body") or ""),
        city=detail_city,
        province=detail_province,
        district=str(address.get("addressRegion") or ""),
        neighborhood=str(
            locality or _get(payload, "neighborhood", "district") or ""
        ),
        category=category,
        property_type=property_type,
        deal_type=deal_type,
        total_price=total_price,
        deposit=parse_price(
            price_parts.get("deposit")
            or _get(payload, "deposit", "deposit_amount", "rent_deposit")
        ),
        monthly_rent=parse_price(
            price_parts.get("monthly")
            or _get(payload, "rent", "monthly_rent", "rent_amount")
        ),
        # Sheypoor quotes the unit price directly, so no division is needed.
        price_per_meter=parse_price(
            price_parts.get("per_meter") or _get(payload, "price_per_meter", "unit_price")
        ),
        area=parse_float(floor_size.get("value") or _get(payload, "area", "built_area", "size")),
        land_area=parse_float(_get(payload, "land_area", "plot_area")),
        rooms=parse_int(item.get("numberOfRooms") or _get(payload, "rooms", "room_count")),
        year_built=parse_int(
            _get(payload, "year_built", "build_year", "construction_year")
        ),
        floor=parse_int(_get(payload, "floor", "floor_number")),
        total_floors=parse_int(_get(payload, "total_floors", "floors_count")),
        has_elevator=flags.get("has_elevator", parse_bool(_get(payload, "elevator", "has_elevator"))),
        has_parking=flags.get("has_parking", parse_bool(_get(payload, "parking", "has_parking"))),
        has_storage=flags.get("has_storage", parse_bool(_get(payload, "storage", "has_storage"))),
        has_balcony=flags.get("has_balcony", parse_bool(_get(payload, "balcony", "has_balcony"))),
        # Sheypoor publishes real coordinates, unlike Divar's fuzzed ones.
        latitude=_to_float(geo.get("latitude") or _get(payload, "latitude", "lat")),
        longitude=_to_float(geo.get("longitude") or _get(payload, "longitude", "lng", "lon")),
        images=_image_list(payload),
        phone=phone,
        agent_name=str(_get(payload, "agency_name", "broker_name") or "") or None,
        business_type=str(_get(payload, "business_type") or "") or None,
        raw=payload,
    )


def _deal_from_offer_category(value: str) -> DealType | None:
    """Read the deal side off the Offer's own ``category`` ("forSale"/"forRent")."""
    slug = (value or "").strip().lower()
    if "rent" in slug:
        return DealType.RENT
    if "sale" in slug:
        return DealType.SALE
    return None


__all__ = ["parse_sheypoor_search", "parse_sheypoor_detail", "_price_parts"]