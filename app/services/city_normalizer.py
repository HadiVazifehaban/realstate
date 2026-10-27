"""Canonical city normaliser for every ingestion path.

Problem: ``Property.city`` is the exact-match key behind the City Gate filter
(``GET /api/v1/properties?city=...``).  Scraped payloads sometimes carry a
neighbourhood (``پونک``), a phase (``فاز ۱``) or a street (``خیابان ...``) in
the city slot, and those rows silently vanish the moment a user picks a real
city.

Rule: a value that is not a known Iranian city is *not* a city -- it belongs
in ``neighborhood``.  This module is the single place that decision lives, so
the scraper sanitiser, the manual submission path and the one-off backfill
cannot drift apart.
"""

from __future__ import annotations

import re

from app.services.location_catalog import catalog, normalized_name

# Canonical city names (Persian), matching the Shekarchi City Gate list and
# the Divar registry's ``persian`` column.  Kept as a literal set: it must work
# without a DB round-trip inside the sanitiser hot path.
KNOWN_CITIES: frozenset[str] = frozenset(
    {
        "تهران",
        "مشهد",
        "شیراز",
        "اصفهان",
        "کرج",
        "کیش",
        "تبریز",
        "اهواز",
        "قم",
        "رشت",
        "ارومیه",
        "کرمانشاه",
        "کرمان",
        "یزد",
        "اراک",
        "زنجان",
        "قزوین",
        "ساری",
        "بابل",
        "آمل",
        "گرگان",
        "نیشابور",
        "سبزوار",
        "بندرعباس",
        "بوشهر",
        "خرم‌آباد",
        "سنندج",
        "ایلام",
        "شهرکرد",
        "یاسوج",
        "بیرجند",
        "بجنورد",
        "سمنان",
        "زاهدان",
        "اردبیل",
        "همدان",
        "کاشان",
        "دزفول",
        "آبادان",
        "خرمشهر",
        "مراغه",
        "میاندوآب",
        "مهاباد",
        "نجف‌آباد",
        "خمینی‌شهر",
        "شاهین‌شهر",
        "ملارد",
        "شهریار",
        "ورامین",
        "پردیس",
        "پرند",
        "اندیشه",
        "لواسان",
        "دماوند",
        "فردیس",
        "نظرآباد",
        "هشتگرد",
        "رباط‌کریم",
        "اسلام‌شهر",
        "پاکدشت",
        "قرچک",
        "قدس",
    }
)

# Latin slugs the Divar/Sheypoor APIs themselves use (city_list, SCRAPER_CITIES,
# trigger payloads).  A slug is as much a city as its Persian name -- without
# these the sanitiser would demote every Latin-slugged row to neighborhood.
LATIN_CITY_SLUGS: frozenset[str] = frozenset(
    {
        "tehran",
        "mashhad",
        "mashad",
        "shiraz",
        "isfahan",
        "esfahan",
        "karaj",
        "kish",
        "tabriz",
        "ahvaz",
        "ahwaz",
        "qom",
        "qom",
        "rasht",
        "urmia",
        "kermanshah",
        "kerman",
        "yazd",
        "arak",
        "zanjan",
        "qazvin",
        "ghazvin",
        "sari",
        "babol",
        "amol",
        "gorgan",
        "neyshabur",
        "sabzevar",
        "bandar-abbas",
        "bushehr",
        "khorramabad",
        "sanandaj",
        "ilam",
        "shahrekord",
        "yasuj",
        "birjand",
        "bojnurd",
        "semnan",
        "zahedan",
        "ardabil",
        "hamadan",
        "kashan",
        "dezful",
        "abadan",
        "khorramshahr",
        "maragheh",
        "miandoab",
        "mahabad",
        "najafabad",
        "khomeinishahr",
        "shahinshahr",
        "malard",
        "shahriar",
        "varamin",
        "pardis",
        "parand",
        "andisheh",
        "lavasan",
        "damavand",
        "fardis",
        "nazarabad",
        "hashtgerd",
        "robatkarim",
        "eslamshahr",
        "pakdasht",
        "qarchak",
        "qods",
    }
)
_NON_CITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"فاز\s*\d+"),
    re.compile(r"خیابان"),
    re.compile(r"بلوار"),
    re.compile(r"شهرک"),
    re.compile(r"^\d+\s*متری"),
    re.compile(r"مرکز\s*شهر"),
    re.compile(r"جاده\s"),
    re.compile(r"گمرک"),
)


def _fold(value: str) -> str:
    """Normalise Persian text for comparison (ye/ke variants, ZWNJ, spaces)."""
    return (
        value.replace("ي", "ی")
        .replace("ى", "ی")
        .replace("ك", "ک")
        .replace("‌", "")
        .replace(" ", "")
        .strip()
    )


_FOLDED_KNOWN: frozenset[str] = frozenset(_fold(name) for name in KNOWN_CITIES)
_CATALOG_NAMES = frozenset(
    normalized_name(c["name"]) for p in catalog()["provinces"] for c in p["cities"]
)


def is_known_city(value: str | None) -> bool:
    """True when the value names a real city (fold-tolerant, Persian or slug)."""
    if not value:
        return False
    text = value.strip()
    if not text:
        return False
    if normalized_name(text) in _CATALOG_NAMES:
        return True
    if any(pattern.search(text) for pattern in _NON_CITY_PATTERNS):
        return False
    if text.lower() in LATIN_CITY_SLUGS:
        return True
    return _fold(text) in _FOLDED_KNOWN


def normalize_city_neighborhood(
    city: str | None, neighborhood: str | None
) -> tuple[str, str]:
    """Split a (city, neighborhood) pair into its canonical form.

    Returns ``(city, neighborhood)`` where city is either a known city or
    ``""``.  A non-city value in the city slot is demoted to neighborhood
    (when that slot is empty), never silently kept as a city.
    """
    raw_city = (city or "").strip()
    raw_area = (neighborhood or "").strip()
    if is_known_city(raw_city):
        return raw_city, raw_area
    if raw_city and not raw_area:
        return "", raw_city
    if raw_city and raw_city not in raw_area:
        return "", f"{raw_area} {raw_city}".strip() if raw_area else raw_city
    return "", raw_area
