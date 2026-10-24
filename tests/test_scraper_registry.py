"""Source registry: routing a scrape job to the right portal.

The registry exists because the pipeline used to import Divar directly, which
made every second source unreachable. These tests pin the properties that make a
new source actually reachable rather than merely written.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.enums import PropertySource  # noqa: E402
from app.services.scraper import cities  # noqa: E402
from app.services.scraper.registry import (  # noqa: E402
    SOURCES,
    ScraperSource,
    UnknownSourceError,
    UnifiedListingDetail,
    UnifiedListingSummary,
    get_source,
    register_source,
    source_keys,
)


def test_every_portal_is_registered() -> None:
    assert source_keys() == ("delta", "divar", "sheypoor")
    assert get_source("divar").client_factory.__name__ == "DivarClient"
    # The regression this registry was added for: Sheypoor existed as code and
    # tests, but nothing could route a job to it.
    assert get_source("sheypoor").client_factory.__name__ == "SheypoorClient"
    # Delta, likewise: a third source that must be reachable by key alone.
    assert get_source("delta").client_factory.__name__ == "DeltaClient"


def test_source_lookup_is_case_insensitive_and_defaults() -> None:
    assert get_source("DIVAR").key == "divar"
    assert get_source("  sheypoor ").key == "sheypoor"
    assert get_source(None).key == "divar"
    assert get_source("").key == "divar"


def test_unknown_source_names_the_registered_ones() -> None:
    with pytest.raises(UnknownSourceError) as excinfo:
        get_source("bayreal")
    message = str(excinfo.value)
    assert "bayreal" in message
    assert "delta" in message
    assert "divar" in message and "sheypoor" in message


def test_each_source_stamps_its_own_property_source() -> None:
    assert get_source("divar").property_source is PropertySource.DIVAR_SCRAPER
    assert get_source("sheypoor").property_source is PropertySource.SHEYPOOR
    assert get_source("delta").property_source is PropertySource.DELTA


def test_only_sources_with_an_extractor_advertise_phone_support() -> None:
    # PhoneExtractor is a Divar session/OTP flow; letting another source accept
    # fetch_phones would collect nothing and report a clean run.
    assert get_source("divar").supports_phone_extraction is True
    assert get_source("sheypoor").supports_phone_extraction is False
    # Delta gates the broker's number behind an authenticated session.
    assert get_source("delta").supports_phone_extraction is False


def test_external_id_prefix_is_unique_per_source_and_absent_for_divar() -> None:
    prefixes = [spec.external_id_prefix for spec in SOURCES.values()]
    # external_id is globally unique, so two sources sharing a prefix (or both
    # using the bare token) would overwrite each other's rows.
    assert len(set(prefixes)) == len(prefixes)
    assert get_source("divar").external_id_prefix == ""
    assert get_source("sheypoor").external_id_prefix
    assert get_source("delta").external_id_prefix == "delta:"


def test_only_sources_with_a_city_registry_validate_it() -> None:
    get_source("divar").validate_city("tehran")
    with pytest.raises(cities.UnknownCityError):
        get_source("divar").validate_city("atlantis")
    # Sheypoor has no local id table, so it accepts the slug shape instead of
    # rejecting everything.
    assert get_source("sheypoor").validate_city("tehran") is None
    assert get_source("sheypoor").validate_districts is None
    # Delta has its own slug registry, so an unknown city is a hard error rather
    # than a 404 that yields zero listings.
    assert get_source("delta").validate_city("Tehran") == "tehran"
    with pytest.raises(ValueError):
        get_source("delta").validate_city("atlantis")


def test_divar_district_validation_still_rejects_unknown_slugs() -> None:
    get_source("divar").validate_districts("tehran", ["tehran-saat-abad"])
    with pytest.raises(cities.UnknownDistrictError):
        get_source("divar").validate_districts("tehran", ["tehran-nowhere"])


def test_parses_produce_the_unified_schema() -> None:
    # Both portals must emit the *same* models, otherwise the deduplicator and
    # sanitiser in the shared pipeline cannot be reused.
    for spec in SOURCES.values():
        summaries = spec.parse_search({"list_widgets": []})
        assert summaries == []
        detail = spec.parse_detail({"title": "x"}, "tok")
        assert isinstance(detail, UnifiedListingDetail)
    assert UnifiedListingSummary.__name__ == "DivarListingSummary"


def test_register_source_rejects_a_silent_overwrite() -> None:
    original = SOURCES["divar"]
    spec = replace(original, label="clone")
    with pytest.raises(ValueError, match="already registered"):
        register_source(spec)
    # replace=True is the explicit opt-in.
    try:
        register_source(spec, replace=True)
        assert SOURCES["divar"].label == "clone"
    finally:
        SOURCES["divar"] = original


def test_scraper_source_requires_a_client_and_parsers() -> None:
    spec = ScraperSource(
        key="demo",
        label="دمو",
        property_source=PropertySource.MLS_IMPORT,
        client_factory=lambda settings=None: None,  # type: ignore[arg-type,return-value]
        parse_search=lambda payload: [],
        parse_detail=lambda payload, token, **kw: UnifiedListingDetail(token=token),
    )
    # A new portal needs no changes anywhere but this registry.
    assert spec.external_id_prefix == ""
    assert spec.supports_phone_extraction is False
    assert spec.validate_city is None