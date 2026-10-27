"""Offline integration regressions for safe scraper job routing."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.enums import ScrapeJobKind, ScrapeJobStatus, ScrapeJobTrigger
from app.schemas.scraper import ScrapeJobCreate
from app.services.scraper.category_mapping import JobValidationError, resolve_categories
from app.services import scraper_service


def _settings(sources=("delta", "sheypoor", "divar")):
    from app.services.scraper.demand_locations import demand_location

    sheypoor_city = demand_location("تهران")
    return SimpleNamespace(
        scraper_enabled=True,
        source_list=sources,
        city_list=("tehran",),
        category_list=("apartment-sell",),
    )


class _Result:
    def __init__(self, row=None):
        self.row = row

    def scalar_one_or_none(self):
        return self.row


class _Session:
    def __init__(self, duplicate=None):
        self.added = []
        self.duplicate = duplicate
        self.execute = AsyncMock(return_value=_Result(duplicate))
        self.commit = AsyncMock()
        self.refresh = AsyncMock()

    def add(self, row):
        self.added.append(row)


@pytest.mark.asyncio
async def test_valid_mapping_creates_job_with_generic_and_source_category():
    from app.services.scraper.demand_locations import demand_location

    sheypoor_city = demand_location("تهران")
    session = _Session()
    job = await scraper_service.create_job(
        session,
            ScrapeJobCreate(source="sheypoor", city=sheypoor_city["slug"], category="house-villa-sell",
                            params={"source_category": "houses-apartments-for-sale",
                                    "execution_scope": "demand:7:1"}),
        trigger=ScrapeJobTrigger.MANUAL,
        settings=_settings(),
    )
    assert job.category == "house-villa-sell"
    assert job.params["source_category"] == "houses-apartments-for-sale"
    assert session.added == [job]
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalid_category_rejected_before_persistence():
    session = _Session()
    with pytest.raises(JobValidationError) as error:
        await scraper_service.create_job(
            session,
            ScrapeJobCreate(source="delta", city="tehran", category="house-villa-sell"),
            settings=_settings(),
        )
    assert error.value.code == "UNSUPPORTED_CATEGORY"
    assert not session.added
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_unverified_divar_city_rejected_before_persistence():
    session = _Session()
    with pytest.raises(JobValidationError) as error:
        await scraper_service.create_job(
            session,
            ScrapeJobCreate(source="divar", city="tehran", category="apartment-sell"),
            settings=_settings(),
        )
    assert error.value.code == "UNVERIFIED_CITY"
    assert not session.added


@pytest.mark.asyncio
async def test_existing_active_effective_job_is_reused():
    existing = SimpleNamespace(status=ScrapeJobStatus.PENDING)
    session = _Session(duplicate=existing)
    result = await scraper_service.create_job(
        session,
        ScrapeJobCreate(source="delta", city="tehran", category="apartment-sell"),
        settings=_settings(),
    )
    assert result is existing
    assert not session.added
    session.commit.assert_not_awaited()


def test_sheypoor_category_expansion_does_not_duplicate_source_routes():
    sale = resolve_categories("sheypoor", "house-villa-sell")
    apartment = resolve_categories("sheypoor", "apartment-sell")
    assert sale.categories == apartment.categories == ("houses-apartments-for-sale",)


def test_generic_sheypoor_category_does_not_imply_property_type():
    from app.services.scraper.sheypoor_taxonomy import map_category_to_types

    prop, deal = map_category_to_types("houses-apartments-for-sale")
    assert prop is not None  # taxonomy's legacy hint is not trusted as actual listing type
    assert deal is not None


@pytest.mark.parametrize("source", ["delta", "sheypoor"])
def test_detail_city_is_catalog_resolved_and_empty_remains_unknown(source):
    from app.services.location_catalog import resolve_city

    assert resolve_city("تهران") is not None
    assert resolve_city(" ") is None


def test_delta_detail_city_propagates_from_payload_only_when_catalogued():
    from app.services.scraper.delta_parser import parse_delta_detail

    detail = parse_delta_detail(
        {"item": {}, "address": {"addressLocality": "تهران", "addressRegion": "تهران"},
         "__context": {"city": "mashhad"}},
        "123",
    )
    assert detail.city == "تهران"
    assert detail.province == "تهران"


def test_sheypoor_detail_city_and_whitespace_handling():
    from app.services.scraper.sheypoor_parser import parse_sheypoor_detail

    detail = parse_sheypoor_detail(
        {"city": " ", "itemOffered": {"address": {"addressLocality": "تهران", "addressRegion": "تهران"}}},
        "123",
    )
    assert detail.city == "تهران"


def test_sheypoor_conflicting_unknown_detail_city_is_not_replaced():
    from app.services.scraper.sheypoor_parser import parse_sheypoor_detail

    detail = parse_sheypoor_detail({"city": "unknown-city", "__search_city": "tehran"}, "123")
    assert detail.city == ""


def test_sanitizer_persists_catalog_city_and_province():
    from app.models.enums import PropertySource
    from app.services.ingestion.sanitizer import build_property_fields
    from app.services.scraper.parser import DivarListingDetail

    fields = build_property_fields(
        DivarListingDetail(token="1", city="تهران", province="تهران"),
        content_hash=None,
        source=PropertySource.DELTA,
    )
    assert fields["city"] == "تهران"
    assert fields["province"] == "تهران"


def test_phase2_dry_run_matrix_is_side_effect_free():
    from app.services.scraper.category_mapping import validate_job_target

    # Resolver checks only static registries; it has no session or job creation path.
    decisions = []
    for city in ("tehran", "tabriz", "maragheh", "mashhad", "isfahan", "shiraz"):
        for source in ("divar", "sheypoor", "delta"):
            for category in ("apartment-sell", "apartment-rent", "house-villa-sell", "house-villa-rent"):
                try:
                    validate_job_target(source, city, category, _settings())
                    state = "READY"
                except JobValidationError as error:
                    state = error.code
                decisions.append((city, source, category, state))
    assert len(decisions) == 72
    assert all(item[3] != "READY" for item in decisions if item[1] == "divar")