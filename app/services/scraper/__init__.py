"""Divar autonomous ingestion (Phase 2): stealth client, parser, phone extractor."""

from app.services.scraper.divar_client import (
    DivarClient,
    ScraperBlockedError,
    ScraperError,
    ScraperResponseError,
    StealthClient,
)
from app.services.scraper.parser import (
    DivarListingDetail,
    DivarListingSummary,
    is_transferable_category,
    map_category,
    parse_bool,
    parse_float,
    parse_int,
    parse_post_detail,
    parse_price,
    parse_search_response,
)
from app.services.scraper.phone_extractor import PhoneExtractor, parse_phone
from app.services.scraper.registry import (
    SOURCES,
    ScraperSource,
    UnifiedListingDetail,
    UnifiedListingSummary,
    UnknownSourceError,
    get_source,
    register_source,
    source_keys,
)
from app.services.scraper.sheypoor_client import SheypoorClient
from app.services.scraper.sheypoor_parser import (
    parse_sheypoor_detail,
    parse_sheypoor_search,
)

__all__ = [
    "DivarClient",
    "StealthClient",
    "ScraperError",
    "ScraperBlockedError",
    "ScraperResponseError",
    "SheypoorClient",
    "ScraperSource",
    "SOURCES",
    "get_source",
    "register_source",
    "source_keys",
    "UnknownSourceError",
    "UnifiedListingDetail",
    "UnifiedListingSummary",
    "parse_sheypoor_search",
    "parse_sheypoor_detail",
    "DivarListingDetail",
    "DivarListingSummary",
    "parse_post_detail",
    "parse_search_response",
    "parse_price",
    "parse_int",
    "parse_float",
    "parse_bool",
    "map_category",
    "PhoneExtractor",
    "parse_phone",
]
