"""Tolerant parser for Divar web-widget JSON payloads.

Divar returns deeply nested "widget" trees that evolve over time.  The parser is
therefore defensive: it walks every dictionary node and extracts known labels /
keys rather than relying on a fixed path.  Persian/Arabic digits and currency
words are normalised into plain integers (Toman).
"""

from __future__ import annotations

import re
from typing import Any, Iterator

from pydantic import BaseModel, Field

from app.models.enums import DealType, PropertyType

# Persian (۰-۹) and Arabic-Indic (٠-٩) digits -> ASCII
_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"
)
_THOUSANDS = str.maketrans("", "", ",\u060c\u066c\u200c ")

_MULTIPLIERS = {
    "میلیارد": 1_000_000_000,
    "میلیون": 1_000_000,
    "هزار": 1_000,
}

_PRICE_NUMBER_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(میلیارد|میلیون|هزار)?")

# Divar exposes two parallel naming layers for the same taxonomy:
#   * web layer      -> https://divar.ir/s/{city}/{category-slug}
#   * API/internal  -> the ``category`` value sent to /v8/* endpoints
# Both are accepted here so a listing is classified whichever layer it carries.
# See docs/divar_taxonomy.md for the full tree.
_CATEGORY_MAP: dict[str, tuple[PropertyType, DealType]] = {
    # -- Residential: sale ------------------------------------------------------
    "apartment-sell": (PropertyType.APARTMENT, DealType.SALE),
    "buy-apartment": (PropertyType.APARTMENT, DealType.SALE),
    "residential-sell": (PropertyType.APARTMENT, DealType.SALE),
    "house-villa-sell": (PropertyType.VILLA, DealType.SALE),
    "buy-villa": (PropertyType.VILLA, DealType.SALE),
    "penthouse-sell": (PropertyType.PENTHOUSE, DealType.SALE),
    "buy-penthouse": (PropertyType.PENTHOUSE, DealType.SALE),
    "plot-old": (PropertyType.LAND, DealType.SALE),
    "buy-old-house": (PropertyType.LAND, DealType.SALE),
    "garden-villa-sell": (PropertyType.GARDEN, DealType.SALE),
    "buy-garden": (PropertyType.GARDEN, DealType.SALE),
    "land-sell": (PropertyType.LAND, DealType.SALE),
    # -- Residential: rent ------------------------------------------------------
    "apartment-rent": (PropertyType.APARTMENT, DealType.RENT),
    "rent-apartment": (PropertyType.APARTMENT, DealType.RENT),
    "residential-rent": (PropertyType.APARTMENT, DealType.RENT),
    "house-villa-rent": (PropertyType.VILLA, DealType.RENT),
    "rent-villa": (PropertyType.VILLA, DealType.RENT),
    "rent-old-house": (PropertyType.LAND, DealType.RENT),
    "rent-garden": (PropertyType.GARDEN, DealType.RENT),
    # -- Commercial: sale -------------------------------------------------------
    "office-sell": (PropertyType.OFFICE, DealType.SALE),
    "buy-office": (PropertyType.OFFICE, DealType.SALE),
    "store-sell": (PropertyType.STORE, DealType.SALE),
    "buy-store": (PropertyType.STORE, DealType.SALE),
    "commercial-sell": (PropertyType.OFFICE, DealType.SALE),
    "buy-commercial-property": (PropertyType.OFFICE, DealType.SALE),
    "warehouse-sell": (PropertyType.WAREHOUSE, DealType.SALE),
    "buy-warehouse": (PropertyType.WAREHOUSE, DealType.SALE),
    "industrial-sell": (PropertyType.INDUSTRIAL, DealType.SALE),
    "buy-industrial-agricultural-property": (PropertyType.INDUSTRIAL, DealType.SALE),
    # -- Commercial: rent -------------------------------------------------------
    "office-rent": (PropertyType.OFFICE, DealType.RENT),
    "rent-office": (PropertyType.OFFICE, DealType.RENT),
    "store-rent": (PropertyType.STORE, DealType.RENT),
    "rent-store": (PropertyType.STORE, DealType.RENT),
    "commercial-rent": (PropertyType.OFFICE, DealType.RENT),
    "rent-commercial-property": (PropertyType.OFFICE, DealType.RENT),
    "warehouse-rent": (PropertyType.WAREHOUSE, DealType.RENT),
    "rent-warehouse": (PropertyType.WAREHOUSE, DealType.RENT),
    "industrial-rent": (PropertyType.INDUSTRIAL, DealType.RENT),
    "rent-industrial-agricultural-property": (PropertyType.INDUSTRIAL, DealType.RENT),
    # -- Short-term / temporary rent --------------------------------------------
    "suite-apartment": (PropertyType.SUITE, DealType.RENT),
    "temporary-rent": (PropertyType.SUITE, DealType.RENT),
    "rent-temporary": (PropertyType.SUITE, DealType.RENT),
    "villa-rent-temporary": (PropertyType.VILLA, DealType.RENT),
}

# Slugs for services/projects (not transferable properties). They are still
# ingested (an agency may track them) but flagged so downstream scoring can
# de-prioritise them instead of treating them as a normal apartment.
_NON_TRANSFERABLE_CATEGORIES = frozenset(
    {
        "construction-partnership",
        "pre-sell-home",
        "real-estate-services",
    }
)


def is_transferable_category(category: str) -> bool:
    """True when the slug represents a property that can be matched/transferred."""
    return (category or "").strip().lower() not in _NON_TRANSFERABLE_CATEGORIES


# ---------------------------------------------------------------------------
#  Value normalisation
# ---------------------------------------------------------------------------
def normalize_digits(text: str) -> str:
    """Convert Persian/Arabic digits to ASCII."""
    return (text or "").translate(_DIGIT_TRANSLATION)


def parse_int(text: Any) -> int | None:
    """Extract an integer from free text (handles Persian digits)."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
    cleaned = normalize_digits(str(text)).translate(_THOUSANDS)
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    return int(float(match.group(0)))


def parse_price(text: Any) -> int | None:
    """Parse a Toman price such as ``"۲ میلیارد و ۵۰۰ میلیون"``.

    Returns ``None`` for "توافقی" (negotiable) or unparseable values.
    """
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
    value = normalize_digits(str(text))
    if any(word in value for word in ("توافقی", "مذاکره", "رایگان")):
        return None
    value = value.translate(_THOUSANDS)
    total = 0
    found = False
    for match in _PRICE_NUMBER_RE.finditer(value):
        number = float(match.group(1))
        unit = match.group(2)
        multiplier = _MULTIPLIERS.get(unit, 1) if unit else 1
        total += int(number * multiplier)
        found = True
    return total if found else None


def parse_bool(text: Any) -> bool | None:
    """Interpret Persian Yes/No style amenity values."""
    if text is None:
        return None
    if isinstance(text, bool):
        return text
    value = str(text).strip().lower()
    if value in {"دارد", "true", "yes", "1", "بله", "هست"}:
        return True
    if value in {"ندارد", "false", "no", "0", "خیر", "نیست"}:
        return False
    return None


def map_category(category: str) -> tuple[PropertyType, DealType]:
    """Map a Divar category slug to (PropertyType, DealType).

    Handles both naming layers (web slugs and API/internal slugs). Falls back
    to keyword matching so a new Divar slug degrades gracefully instead of
    mis-typing an apartment as, say, a plot of land.
    """
    if not category:
        return PropertyType.APARTMENT, DealType.SALE
    slug = category.strip().lower()
    if slug in _CATEGORY_MAP:
        return _CATEGORY_MAP[slug]
    deal = DealType.RENT if "rent" in slug else DealType.SALE
    # Keyword order matters: "plot"/"land" must win over the generic
    # "apartment" match, and "industrial" over "warehouse".
    for keyword, property_type in _FALLBACK_KEYWORDS:
        if keyword in slug:
            return property_type, deal
    return PropertyType.APARTMENT, deal


# Ordered keyword fallbacks used when an unknown slug arrives.
_FALLBACK_KEYWORDS: tuple[tuple[str, PropertyType], ...] = (
    ("penthouse", PropertyType.PENTHOUSE),
    ("suite", PropertyType.SUITE),
    ("villa", PropertyType.VILLA),
    ("garden", PropertyType.GARDEN),
    ("plot", PropertyType.LAND),
    ("land", PropertyType.LAND),
    ("old-house", PropertyType.LAND),
    ("industrial", PropertyType.INDUSTRIAL),
    ("agricultural", PropertyType.INDUSTRIAL),
    ("warehouse", PropertyType.WAREHOUSE),
    ("store", PropertyType.STORE),
    ("shop", PropertyType.STORE),
    ("office", PropertyType.OFFICE),
    ("commercial", PropertyType.OFFICE),
    ("apartment", PropertyType.APARTMENT),
)


# ---------------------------------------------------------------------------
#  Typed schemas
# ---------------------------------------------------------------------------
class DivarListingSummary(BaseModel):
    """A row from a Divar search result list."""

    token: str
    title: str = ""
    city: str = ""
    district: str = ""
    category: str = ""
    price_hint: str = ""
    image_url: str | None = None
    # Divar's three-line card text (top/middle/bottom_description_text).
    top_description_text: str = ""
    middle_description_text: str = ""
    bottom_description_text: str = ""
    has_chat: bool | None = None
    red_text: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class DivarListingDetail(BaseModel):
    """Normalised detail of a single Divar listing."""

    token: str
    title: str = ""
    description: str = ""

    city: str = ""
    province: str = ""
    district: str = ""
    neighborhood: str = ""
    category: str = ""
    property_type: PropertyType | None = None
    deal_type: DealType | None = None

    total_price: int | None = None
    deposit: int | None = None
    monthly_rent: int | None = None
    price_per_meter: int | None = None
    price_is_convertible: bool | None = None  # "توافقی" / negotiable

    area: float | None = None
    land_area: float | None = None
    rooms: int | None = None
    year_built: int | None = None
    floor: int | None = None
    total_floors: int | None = None
    units_per_floor: int | None = None

    has_elevator: bool | None = None
    has_parking: bool | None = None
    has_storage: bool | None = None
    has_balcony: bool | None = None

    latitude: float | None = None
    longitude: float | None = None
    coordinate_radius: int | None = None  # Divar fuzzes coords by ~150 m
    images: list[str] = Field(default_factory=list)
    phone: str | None = None
    # Divar contact block — business/agent identity (never the owner name).
    business_type: str | None = None
    agent_name: str | None = None
    agent_slug: str | None = None
    #: Agency behind the listing, when the portal names one. Delta publishes it as
    #: ``realEstateAgency``; Divar's contact block carries the equivalent. Kept
    #: separate from ``agent_name`` because the card shows both, and an agency
    #: listing often names a person who is not its owner.
    agency_name: str | None = None
    agency_slug: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
#  Generic traversal helpers
# ---------------------------------------------------------------------------
def iter_dicts(obj: Any) -> Iterator[dict]:
    """Yield every dictionary node inside a nested JSON structure."""
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from iter_dicts(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_dicts(item)


def collect_label_value_pairs(payload: Any) -> dict[str, str]:
    """Build a ``{label: value}`` map from Divar's widget ``title``/``value`` rows."""
    pairs: dict[str, str] = {}
    for node in iter_dicts(payload):
        title = node.get("title") or node.get("label")
        value = node.get("value")
        if value is None:
            value = node.get("subtitle")
        if (
            isinstance(title, str)
            and title.strip()
            and value is not None
            and not isinstance(value, (dict, list))
        ):
            key = title.strip()
            if key not in pairs:
                pairs[key] = str(value).strip()
    return pairs


def _lookup(pairs: dict[str, str], *labels: str) -> str | None:
    """Find the first label (exact then substring) present in ``pairs``."""
    for label in labels:
        if label in pairs:
            return pairs[label]
    for key, value in pairs.items():
        for label in labels:
            if label in key:
                return value
    return None


def find_coordinates(payload: Any) -> tuple[float | None, float | None]:
    """Locate the first lat/lng pair anywhere in the payload."""
    for node in iter_dicts(payload):
        lat = node.get("latitude", node.get("lat"))
        lng = node.get("longitude", node.get("lng", node.get("lon")))
        if lat is None or lng is None:
            continue
        try:
            return float(lat), float(lng)
        except (TypeError, ValueError):
            continue
    return None, None


def find_seo_info(payload: Any) -> dict[str, Any]:
    """Return Divar's ``seo.post_seo_schema`` block, the one *addressed* node.

    Every other helper here walks the payload blindly and takes the first match,
    which is fine for values Divar repeats everywhere (area, price) but wrong for
    identity: the post payload starts with ``sections``, whose very first widget is
    the *agency* profile ("املاک"), so a blind ``title`` lookup yields the agency
    name for every listing. The ``seo`` block is the only place Divar states which
    node is the listing itself:

    ``seo.post_seo_schema`` -- ``name``/``web_info.title`` (the headline as the
    seller typed it), ``web_info.city_persian`` / ``district_persian`` (the human
    place names, where the sibling ``city``/``district`` keys are slugs like
    ``tehran``/``shahrak-e-gharb``), ``geo`` (coordinates) and ``image``.
    """
    for node in iter_dicts(payload):
        seo = node.get("seo")
        if not isinstance(seo, dict):
            continue
        schema = seo.get("post_seo_schema")
        if isinstance(schema, dict):
            return schema
    return {}


def find_seo_web_info(payload: Any) -> dict[str, Any]:
    """``seo.post_seo_schema.web_info`` -- the Persian labels for one listing."""
    web_info = find_seo_info(payload).get("web_info")
    return web_info if isinstance(web_info, dict) else {}


# "… در تهران - ۱۳ مهر ۱۴۰۵" -> the trailing city + date Divar appends to the
# page <title>. The headline itself never contains this shape.
_SEO_TITLE_TAIL_RE = re.compile(r"\s+در\s+[^–-]*\s+[–-]\s*.*$")


def strip_seo_title_tail(title: str) -> str:
    """Drop the `` در {city} - {date}`` tail Divar appends to ``seo.title``."""
    return _SEO_TITLE_TAIL_RE.sub("", title).strip()


def _seo_title_fallback(payload: Any) -> str:
    """Headline for payloads whose ``post_seo_schema.web_info.title`` is absent.

    Prefers the page ``<title>`` (minus its city/date tail) and the H1 widget,
    and only then falls back to the blind ``title`` walk -- which on a post
    payload returns the agency name, so it must stay last.
    """
    for node in iter_dicts(payload):
        seo = node.get("seo")
        if isinstance(seo, dict) and isinstance(seo.get("title"), str):
            cleaned = strip_seo_title_tail(seo["title"])
            if cleaned:
                return cleaned
    for node in iter_dicts(payload):
        heading = node.get("high_level_heading")
        if isinstance(heading, str) and heading.strip():
            return heading.strip()
    return _first_str(payload, ("title",))


def find_cover_image(payload: Any) -> str | None:
    """The listing's own photo, per ``seo.post_seo_schema.image`` / ``seo.image_url``.

    ``collect_images`` sweeps the whole payload, so it also returns the agency's
    logo and unrelated gallery shots; this is the one Divar labels as the post
    image, which is what the card should lead with.
    """
    seo_image = find_seo_info(payload).get("image")
    if isinstance(seo_image, str) and seo_image.startswith("http"):
        return seo_image
    for node in iter_dicts(payload):
        seo = node.get("seo")
        if isinstance(seo, dict) and isinstance(seo.get("image_url"), str):
            return seo["image_url"]
    return None


def find_coordinates(payload: Any) -> tuple[float | None, float | None]:
    """Locate the first lat/lng pair anywhere in the payload."""
    for node in iter_dicts(payload):
        lat = node.get("latitude", node.get("lat"))
        lng = node.get("longitude", node.get("lng", node.get("lon")))
        if lat is None or lng is None:
            continue
        try:
            return float(lat), float(lng)
        except (TypeError, ValueError):
            continue
    return None, None


def find_seo_coordinates(payload: Any) -> tuple[float | None, float | None]:
    """Coordinates from ``seo.post_seo_schema.geo`` — string-encoded on Divar."""
    geo = find_seo_info(payload).get("geo")
    if not isinstance(geo, dict):
        return None, None
    lat = parse_float(geo.get("latitude"))
    lng = parse_float(geo.get("longitude"))
    return lat, lng


def collect_images(payload: Any) -> list[str]:
    """Collect distinct image URLs.

    Handles both shapes Divar returns: a bare ``["https://...jpg", ...]``
    array of strings, and ``{url|src|image|image_url: ...}`` object nodes.
    """
    urls: list[str] = []

    def _add(value: Any) -> None:
        if isinstance(value, str) and value.startswith("http"):
            if any(
                ext in value.lower()
                for ext in (".jpg", ".jpeg", ".png", ".webp")
            ) and value not in urls:
                urls.append(value)

    def _walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for key in ("url", "src", "image", "image_url"):
                _add(obj.get(key))
            for value in obj.values():
                _walk(value)
        elif isinstance(obj, list):
            for item in obj:
                # Bare string array: ["https://cdn.../1.jpg", ...]
                _add(item)
                _walk(item)

    _walk(payload)
    return urls


def find_financial(payload: Any) -> dict[str, Any]:
    """Return Divar's structured ``financial`` block, when present.

    Divar exposes clean numerics (``total_price``, ``deposit``,
    ``monthly_rent``, ``price_per_meter``) that are far more reliable than
    re-parsing the Persian label text, so they take precedence.
    """
    for node in iter_dicts(payload):
        financial = node.get("financial")
        if isinstance(financial, dict) and (
            "total_price" in financial
            or "deposit" in financial
            or "monthly_rent" in financial
        ):
            return financial
    return {}


def collect_amenities(payload: Any) -> dict[str, bool]:
    """Map amenity titles to their availability from ``{title, available}`` rows.

    These are *not* label/value pairs, so they are invisible to
    :func:`collect_label_value_pairs`; without this the elevator/parking flags
    would always stay ``None``.
    """
    amenities: dict[str, bool] = {}
    for node in iter_dicts(payload):
        title = node.get("title") or node.get("label")
        if not isinstance(title, str) or not title.strip():
            continue
        available = node.get("available")
        if available is None:
            available = node.get("has")
        if isinstance(available, bool):
            amenities.setdefault(title.strip(), available)
    return amenities


def find_contact(payload: Any) -> dict[str, Any]:
    """Return Divar's ``contact`` block (phone / agency identity)."""
    for node in iter_dicts(payload):
        contact = node.get("contact")
        if isinstance(contact, dict) and contact:
            return contact
    return {}


def _find_radius(payload: Any) -> int | None:
    """Divar fuzzes coordinates; the radius field tells us by how much."""
    for node in iter_dicts(payload):
        for key in ("radius", "coordinate_radius"):
            value = node.get(key)
            if isinstance(value, (int, float)):
                return int(value)
    return None


def parse_floor_and_total(value: Any) -> tuple[int | None, int | None]:
    """Parse ``"۳ از ۵"`` into ``(floor=3, total_floors=5)``.

    Divar writes the floor and the building height together ("3 of 5", "همکف",
    "زیرزمین"). A single number only sets the floor.
    """
    text = normalize_digits(str(value or ""))
    numbers = re.findall(r"-?\d+", text.translate(_THOUSANDS))
    floor = int(numbers[0]) if numbers else None
    total = int(numbers[1]) if len(numbers) > 1 else None
    # "زیرزمین" (basement) has no numeric floor.
    if floor is None and "زیرزمین" in text:
        floor = -1
    return floor, total


def _extract_token(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    token = node.get("token")
    if isinstance(token, str) and token:
        return token
    action = node.get("action")
    if isinstance(action, dict):
        action_payload = action.get("payload")
        if isinstance(action_payload, dict):
            inner = action_payload.get("token")
            if isinstance(inner, str) and inner:
                return inner
    return None


def _first_str(payload: Any, keys: tuple[str, ...]) -> str:
    for node in iter_dicts(payload):
        for key in keys:
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _find_category(payload: Any) -> str:
    for node in iter_dicts(payload):
        for key in ("category", "category_slug", "cat"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


# ---------------------------------------------------------------------------
#  Public parse entry points
# ---------------------------------------------------------------------------
def parse_search_response(payload: dict) -> list[DivarListingSummary]:
    """Extract listing summaries from a Divar search response."""
    candidates: list[Any] = []
    list_widgets = payload.get("list_widgets")
    if isinstance(list_widgets, list):
        candidates.extend(list_widgets)
    web_widgets = payload.get("web_widgets")
    if isinstance(web_widgets, dict):
        for key in ("post_list", "list_widgets", "post_row"):
            value = web_widgets.get(key)
            if isinstance(value, list):
                candidates.extend(value)

    summaries: list[DivarListingSummary] = []
    seen: set[str] = set()

    def _add(node: dict, container: Any) -> None:
        data = node.get("data") if isinstance(node.get("data"), dict) else node
        token = _extract_token(data) or _extract_token(node)
        if not token or token in seen:
            return
        seen.add(token)
        pairs = collect_label_value_pairs(container)
        top_text = str(data.get("top_description_text") or "")
        middle_text = str(data.get("middle_description_text") or "")
        bottom_text = str(data.get("bottom_description_text") or "")
        red_text = str(data.get("red_text") or "")
        has_chat = data.get("has_chat")
        summaries.append(
            DivarListingSummary(
                token=token,
                title=str(
                    data.get("title")
                    or top_text
                    or _lookup(pairs, "عنوان") or ""
                ),
                city=str(data.get("city") or _lookup(pairs, "شهر") or ""),
                district=str(
                    data.get("district")
                    or _lookup(pairs, "محله", "منطقه") or ""
                ),
                category=str(data.get("category") or ""),
                price_hint=str(
                    data.get("price")
                    or bottom_text
                    or _lookup(pairs, "قیمت") or ""
                ),
                image_url=(
                    str(data.get("image_url"))
                    if isinstance(data.get("image_url"), str)
                    else (collect_images(node) or [None])[0]
                ),
                top_description_text=top_text,
                middle_description_text=middle_text,
                bottom_description_text=bottom_text,
                has_chat=has_chat if isinstance(has_chat, bool) else None,
                red_text=red_text,
                raw=node,
            )
        )

    for widget in candidates:
        if isinstance(widget, dict):
            _add(widget, payload)

    # Fallback: no known container -> scan the whole payload for tokens.
    if not summaries:
        for node in iter_dicts(payload):
            _add(node, payload)

    return summaries


def parse_float(text: Any) -> float | None:
    """Extract a float from free text (handles Persian digits)."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    cleaned = normalize_digits(str(text)).translate(_THOUSANDS)
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    return float(match.group(0)) if match else None


def parse_post_detail(
    payload: dict,
    token: str,
    *,
    phone: str | None = None,
    current_year: int | None = None,
) -> DivarListingDetail:
    """Normalise a Divar post-detail payload into :class:`DivarListingDetail`."""
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    pairs = collect_label_value_pairs(data)
    amenities = collect_amenities(data)
    financial = find_financial(data)
    contact = find_contact(data)

    category = _find_category(data)
    property_type, deal_type = map_category(category)

    # Detect rent listings even when the category slug is missing.
    rent_markers = ("ودیعه", "رهن", "اجاره")
    has_rent_label = any(
        any(marker in key for marker in rent_markers) for key in pairs
    )
    if has_rent_label:
        deal_type = DealType.RENT if deal_type != DealType.SALE else DealType.RENT

    # Prefer Divar's structured numerics; fall back to the Persian label rows.
    price_value = financial.get("total_price")
    deposit = financial.get("deposit")
    rent = financial.get("monthly_rent")
    price_per_meter = financial.get("price_per_meter")
    convertible = financial.get("convertible")
    if price_value is None:
        price_value = parse_price(_lookup(pairs, "قیمت کل", "قیمت"))
    if deposit is None:
        deposit = parse_price(_lookup(pairs, "ودیعه", "رهن"))
    if rent is None:
        rent = parse_price(_lookup(pairs, "اجاره"))
    if price_per_meter is None:
        price_per_meter = parse_price(_lookup(pairs, "قیمت هر متر"))
    if convertible is None:
        raw_price_text = _lookup(pairs, "قیمت کل", "قیمت") or ""
        convertible = parse_price(raw_price_text) is None

    total_price: int | None = None
    if deal_type == DealType.SALE:
        total_price = price_value
    else:
        # For rentals the generic "قیمت" usually means the deposit.
        if deposit is None and price_value is not None:
            deposit = price_value
        elif deposit is not None and price_value is not None:
            total_price = None

    # A lease quoted as a deposit with no monthly rent is a «رهن کامل» (full
    # mortgage): the whole cost is the deposit and no rent follows. Divar never
    # sends a FULL_MORTGAGE category slug — it only leaves the rent field empty
    # — so the distinction has to be read off the numbers here. Without this
    # every deposit-only lease is stored as RENT, and the desk's «رهن کامل»
    # filter returns an empty feed even though the inventory holds such units.
    if deal_type == DealType.RENT and deposit is not None and rent is None:
        deal_type = DealType.FULL_MORTGAGE

    area = parse_float(_lookup(pairs, "متراژ", "مساحت"))
    land_area = parse_float(_lookup(pairs, "متراژ زمین", "مساحت زمین"))

    year_built = parse_int(_lookup(pairs, "سال ساخت", "سال‌ساخت", "ساخت"))
    if year_built is None:
        age = parse_int(_lookup(pairs, "سن بنا"))
        if age is not None and current_year is not None:
            year_built = current_year - age

    # The SEO block addresses the listing itself, so it outranks the blind walk
    # for identity (headline, place names, pin) -- see ``find_seo_info``.
    seo_info = find_seo_info(data)
    web_info = find_seo_web_info(data)

    latitude, longitude = find_seo_coordinates(data)
    if latitude is None or longitude is None:
        latitude, longitude = find_coordinates(data)

    # "طبقه" carries "3 of 5" -> (floor, total_floors)
    floor, total_floors = parse_floor_and_total(_lookup(pairs, "طبقه"))
    if total_floors is None:
        total_floors = parse_int(_lookup(pairs, "تعداد طبقات", "کل طبقات"))

    # Amenities may arrive as {title, available} rows or as label/value pairs.
    def _amenity(*labels: str) -> bool | None:
        for label in labels:
            if label in amenities:
                return amenities[label]
            parsed = parse_bool(_lookup(pairs, label))
            if parsed is not None:
                return parsed
        return None

    district = (
        str(web_info.get("district_persian") or "").strip()
        or _first_str(data, ("district",))
        or _lookup(pairs, "محله", "منطقه")
        or ""
    )
    # Divar sometimes returns the phone inline in ``contact.phone``; use it
    # when the dedicated (session-gated) extractor did not provide one.
    # Imported lazily: phone_extractor imports this module for its helpers.
    phone_value = phone
    if phone_value is None and contact:
        from app.services.scraper.phone_extractor import parse_phone as _parse_phone

        phone_value = _parse_phone(contact)

    # Cover first: the pipeline marks index 0 as ``is_cover``, and the card leads
    # with it. The rest follow in the order ``collect_images`` swept them.
    gallery = collect_images(data)
    cover = find_cover_image(data)
    images = [cover, *[url for url in gallery if url != cover]] if cover else gallery

    return DivarListingDetail(
        token=token,
        title=(
            str(web_info.get("title") or "").strip()
            or str(seo_info.get("name") or "").strip()
            or _seo_title_fallback(data)
        ),
        description=_first_str(data, ("description",)) or "",
        city=(
            str(web_info.get("city_persian") or "").strip()
            or _first_str(data, ("city",))
            or (_lookup(pairs, "شهر") or "")
        ),
        district=district,
        neighborhood=district,
        category=category,
        property_type=property_type,
        deal_type=deal_type,
        total_price=total_price,
        deposit=deposit,
        monthly_rent=rent,
        price_per_meter=price_per_meter,
        price_is_convertible=bool(convertible),
        area=area,
        land_area=land_area,
        rooms=parse_int(_lookup(pairs, "اتاق", "خواب")),
        year_built=year_built,
        floor=floor,
        total_floors=total_floors,
        units_per_floor=parse_int(_lookup(pairs, "تعداد واحد در طبقه", "واحد در طبقه")),
        has_elevator=_amenity("آسانسور", "لیفت"),
        has_parking=_amenity("پارکینگ"),
        has_storage=_amenity("انباری", "انبار"),
        has_balcony=_amenity("بالکن", "تراس"),
        latitude=latitude,
        longitude=longitude,
        coordinate_radius=parse_int(_find_radius(data)),
        images=images,
        phone=phone_value,
        business_type=_first_str(data, ("business_type",)) or contact.get("business_type"),
        agent_name=_first_str(data, ("agent_name",)) or contact.get("agent_name"),
        agent_slug=_first_str(data, ("slug",)) or contact.get("slug"),
        agency_name=_first_str(data, ("agency_name",)) or contact.get("agency_name"),
        agency_slug=_first_str(data, ("agency_slug",)) or contact.get("agency_slug"),
        raw=payload,
    )
