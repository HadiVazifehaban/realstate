"""Unified city mapping for all scraper platforms.

This module maps Persian city names to platform-specific identifiers:
- Divar: city_id and slug
- Sheypoor: province and city slugs
- Delta: city_id
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PlatformCityMeta:
    """Platform-specific identifiers for a city."""
    divar_slug: str
    divar_city_id: int
    sheypoor_province: str
    sheypoor_city: str
    delta_city_id: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


# Unified city mapping for all platforms
CITY_MAPPING: dict[str, PlatformCityMeta] = {
    "تهران": PlatformCityMeta(
        divar_slug="tehran",
        divar_city_id=1,
        sheypoor_province="tehran",
        sheypoor_city="tehran",
        delta_city_id=1,
        lat=35.6892,
        lon=51.3890,
    ),
    "مشهد": PlatformCityMeta(
        divar_slug="mashhad",
        divar_city_id=2,
        sheypoor_province="khorasan-razavi",
        sheypoor_city="mashhad",
        delta_city_id=2,
        lat=36.2972,
        lon=59.6067,
    ),
    "اصفهان": PlatformCityMeta(
        divar_slug="isfahan",
        divar_city_id=3,
        sheypoor_province="isfahan",
        sheypoor_city="isfahan",
        delta_city_id=3,
        lat=32.6546,
        lon=51.6680,
    ),
    "شیراز": PlatformCityMeta(
        divar_slug="shiraz",
        divar_city_id=4,
        sheypoor_province="fars",
        sheypoor_city="shiraz",
        delta_city_id=4,
        lat=29.5918,
        lon=52.5837,
    ),
    "تبریز": PlatformCityMeta(
        divar_slug="tabriz",
        divar_city_id=5,
        sheypoor_province="azarbaijan-east",
        sheypoor_city="tabriz",
        delta_city_id=5,
        lat=38.0962,
        lon=46.2738,
    ),
    "شبستر": PlatformCityMeta(
        divar_slug="shabestar",
        divar_city_id=23,
        sheypoor_province="azarbaijan-east",
        sheypoor_city="shabestar",
        delta_city_id=23,
        lat=38.1389,
        lon=45.6969,
    ),
    "کرج": PlatformCityMeta(
        divar_slug="karaj",
        divar_city_id=6,
        sheypoor_province="alborz",
        sheypoor_city="karaj",
        delta_city_id=6,
        lat=35.8400,
        lon=50.9391,
    ),
    "اهواز": PlatformCityMeta(
        divar_slug="ahvaz",
        divar_city_id=7,
        sheypoor_province="khuzestan",
        sheypoor_city="ahvaz",
        delta_city_id=7,
        lat=31.3183,
        lon=48.6706,
    ),
    "کرمانشاه": PlatformCityMeta(
        divar_slug="kermanshah",
        divar_city_id=8,
        sheypoor_province="kermanshah",
        sheypoor_city="kermanshah",
        delta_city_id=8,
        lat=34.3317,
        lon=47.0778,
    ),
    "ارومیه": PlatformCityMeta(
        divar_slug="urmia",
        divar_city_id=9,
        sheypoor_province="azarbaijan-west",
        sheypoor_city="urmia",
        delta_city_id=9,
        lat=37.5527,
        lon=45.0762,
    ),
    "رشت": PlatformCityMeta(
        divar_slug="rasht",
        divar_city_id=10,
        sheypoor_province="gilan",
        sheypoor_city="rasht",
        delta_city_id=10,
        lat=37.2808,
        lon=49.5832,
    ),
    "زنجان": PlatformCityMeta(
        divar_slug="zanjan",
        divar_city_id=11,
        sheypoor_province="zanjan",
        sheypoor_city="zanjan",
        delta_city_id=11,
        lat=36.6767,
        lon=48.5087,
    ),
    "همدان": PlatformCityMeta(
        divar_slug="hamadan",
        divar_city_id=12,
        sheypoor_province="hamadan",
        sheypoor_city="hamadan",
        delta_city_id=12,
        lat=34.7959,
        lon=48.5138,
    ),
    "یزد": PlatformCityMeta(
        divar_slug="yazd",
        divar_city_id=13,
        sheypoor_province="yazd",
        sheypoor_city="yazd",
        delta_city_id=13,
        lat=31.8974,
        lon=54.3675,
    ),
    "اردبیل": PlatformCityMeta(
        divar_slug="ardabil",
        divar_city_id=14,
        sheypoor_province="ardabil",
        sheypoor_city="ardabil",
        delta_city_id=14,
        lat=38.2508,
        lon=48.2933,
    ),
    "بندرعباس": PlatformCityMeta(
        divar_slug="bandar-abbas",
        divar_city_id=15,
        sheypoor_province="hormozgan",
        sheypoor_city="bandar-abbas",
        delta_city_id=15,
        lat=27.1957,
        lon=56.2718,
    ),
    "اراک": PlatformCityMeta(
        divar_slug="arak",
        divar_city_id=16,
        sheypoor_province="markazi",
        sheypoor_city="arak",
        delta_city_id=16,
        lat=34.0946,
        lon=49.6960,
    ),
    "قم": PlatformCityMeta(
        divar_slug="qom",
        divar_city_id=18,
        sheypoor_province="qom",
        sheypoor_city="qom",
        delta_city_id=18,
        lat=34.6416,
        lon=50.8746,
    ),
    "بابل": PlatformCityMeta(
        divar_slug="babol",
        divar_city_id=19,
        sheypoor_province="mazandaran",
        sheypoor_city="babol",
        delta_city_id=19,
        lat=36.5493,
        lon=52.6764,
    ),
    "گرگان": PlatformCityMeta(
        divar_slug="gorgan",
        divar_city_id=20,
        sheypoor_province="golestan",
        sheypoor_city="gorgan",
        delta_city_id=20,
        lat=36.8406,
        lon=54.4385,
    ),
    "ساری": PlatformCityMeta(
        divar_slug="sari",
        divar_city_id=21,
        sheypoor_province="mazandaran",
        sheypoor_city="sari",
        delta_city_id=21,
        lat=36.5603,
        lon=53.0598,
    ),
    "کرمان": PlatformCityMeta(
        divar_slug="kerman",
        divar_city_id=22,
        sheypoor_province="kerman",
        sheypoor_city="kerman",
        delta_city_id=22,
        lat=30.2839,
        lon=57.0832,
    ),
}


def get_city_meta(city_name: str) -> Optional[PlatformCityMeta]:
    """Get platform-specific metadata for a Persian city name."""
    return CITY_MAPPING.get(city_name)


def get_supported_cities() -> list[str]:
    """Return list of supported Persian city names."""
    return sorted(CITY_MAPPING.keys())


__all__ = [
    "PlatformCityMeta",
    "CITY_MAPPING",
    "get_city_meta",
    "get_supported_cities",
]
