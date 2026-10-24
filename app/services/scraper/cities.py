"""Divar city/district registry.

Divar's **web layer** addresses cities by slug (``/s/tehran/...``) while the
**API layer** (``api.divar.ir/v8/postlist/w/search``) expects numeric
``city_ids``.  This module is the single source of truth that bridges the two.

Keeping the ids in code (rather than guessing on the fly) means a typo in
``SCRAPER_CITIES`` fails fast with a helpful message instead of silently
returning zero listings.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DivarCity:
    """A city Divar indexes, with its internal numeric id."""

    slug: str          # web-layer slug, e.g. "tehran"
    city_id: int       # API-layer id, e.g. 1
    persian: str       # human label for error messages
    districts: dict[str, int] = field(default_factory=dict)
    is_verified: bool = False  # True once confirmed against the live API


# Known cities and their neighbourhood slugs.
#
# ID PROVENANCE (important): these are Divar's internal numeric ids as used by
# ``/v8/postlist/w/search``. They are **not** verified against the live API by
# this codebase, because the dev/CI environment cannot reach api.divar.ir
# (it answers 403 AccessDenied). Treat them as a starting point and refresh
# with ``python -m app.cli.divar_cities --refresh`` from an egress IP that
# Divar accepts. ``is_verified=False`` propagates into the search payload so a
# stale registry is visible in logs rather than silently returning 0 listings.
CITIES: tuple[DivarCity, ...] = (
    DivarCity("tehran", 1, "تهران", {
        "tehran-saat-abad": 1529,
        "tehran-karaj": 1240,
    }),
    DivarCity("mashhad", 2, "مشهد", {}),
    DivarCity("isfahan", 3, "اصفهان", {}),
    DivarCity("shiraz", 4, "شیراز", {}),
    DivarCity("tabriz", 5, "تبریز", {}),
    DivarCity("karaj", 6, "کرج", {}),
    DivarCity("ahvaz", 7, "اهواز", {}),
    DivarCity("kermanshah", 8, "کرمانشاه", {}),
    DivarCity("urmia", 9, "ارومیه", {}),
    DivarCity("rasht", 10, "رشت", {}),
    DivarCity("zanjan", 11, "زنجان", {}),
    DivarCity("hamadan", 12, "همدان", {}),
    DivarCity("yazd", 13, "یزد", {}),
    DivarCity("ardabil", 14, "اردبیل", {}),
    DivarCity("bandar-abbas", 15, "بندرعباس", {}),
    DivarCity("arak", 16, "اراک", {}),
    DivarCity("qom", 18, "قم", {}),
    DivarCity("babol", 19, "بابل", {}),
    DivarCity("gorgan", 20, "گرگان", {}),
    DivarCity("sari", 21, "ساری", {}),
    DivarCity("kerman", 22, "کرمان", {}),
)

_BY_SLUG: dict[str, DivarCity] = {c.slug: c for c in CITIES}

# Persian labels / common aliases users may type into SCRAPER_CITIES.
_ALIASES: dict[str, str] = {
    "تهران": "tehran",
    "مشهد": "mashhad",
    "اصفهان": "isfahan",
    "شیراز": "shiraz",
    "تبریز": "tabriz",
    "کرج": "karaj",
    "اهواز": "ahvaz",
    "کرمانشاه": "kermanshah",
    "رشت": "rasht",
    "یزد": "yazd",
    "قم": "qom",
    "کرمان": "kerman",
}


class UnknownCityError(ValueError):
    """Raised when a city slug/alias is not present in the registry."""

    def __init__(self, city: str, known: list[str]) -> None:
        self.city = city
        self.known = known
        super().__init__(
            f"Unknown Divar city {city!r}. Known cities: {', '.join(known)}"
        )


class UnknownDistrictError(ValueError):
    """Raised when a district slug is not registered for a city."""

    def __init__(self, city: str, district: str, known: list[str]) -> None:
        super().__init__(
            f"Unknown district {district!r} for city {city!r}. "
            f"Known districts: {', '.join(known) or '(none registered)'}"
        )


def normalize_city_slug(city: str) -> str:
    """Normalise a user-supplied city name to its canonical slug."""
    raw = (city or "").strip().lower()
    return _ALIASES.get(raw, raw)


def get_city(city: str) -> DivarCity:
    """Resolve a city slug/alias to its registry entry.

    Raises :class:`UnknownCityError` listing valid slugs when not found.
    """
    slug = normalize_city_slug(city)
    found = _BY_SLUG.get(slug)
    if found is None:
        raise UnknownCityError(city, sorted(_BY_SLUG))
    return found


def resolve_city_id(city: str) -> int:
    """Return the numeric ``city_id`` the Divar API expects."""
    return get_city(city).city_id


def resolve_district_ids(city: str, districts: list[str] | tuple[str, ...]) -> list[int]:
    """Map district slugs to their numeric ids for one city."""
    entry = get_city(city)
    ids: list[int] = []
    for district in districts:
        slug = (district or "").strip().lower()
        found = entry.districts.get(slug)
        if found is None:
            raise UnknownDistrictError(
                entry.slug, district, sorted(entry.districts)
            )
        if found not in ids:
            ids.append(found)
    return ids


def known_city_slugs() -> list[str]:
    """All canonical city slugs (for CLI/help output)."""
    return sorted(_BY_SLUG)


def unverified_cities() -> list[DivarCity]:
    """Cities whose ids have never been confirmed against the live API."""
    return [c for c in CITIES if not c.is_verified]


def format_registry_markdown() -> str:
    """Render the registry as a markdown table for ``--refresh`` output."""
    lines = [
        "| slug | city_id | persian | districts | verified |",
        "|---|---|---|---|---|",
    ]
    for c in CITIES:
        districts = ", ".join(f"{k}={v}" for k, v in sorted(c.districts.items()))
        lines.append(
            f"| {c.slug} | {c.city_id} | {c.persian} | {districts or '-'} "
            f"| {'yes' if c.is_verified else 'no'} |"
        )
    return "\n".join(lines)


__all__ = [
    "CITIES",
    "DivarCity",
    "UnknownCityError",
    "UnknownDistrictError",
    "get_city",
    "known_city_slugs",
    "normalize_city_slug",
    "resolve_city_id",
    "resolve_district_ids",
]