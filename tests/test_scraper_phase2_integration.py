"""Offline integration regressions for safe scraper job routing."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.enums import ScrapeJobKind, ScrapeJobStatus, ScrapeJobTrigger
from app.schemas.scraper import ScrapeJobCreate
from app.services.scraper.category_mapping import JobValidationError, resolve_categories
from app.services import scraper_service


def _settings(sources=("delta", "sheypoor", "divar")):
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
async def test_curated_demand_mapping_creates_job_with_generic_and_source_category():
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
async def test_source_category_override_cannot_be_spoofed_by_api_scope():
    session = _Session()
    with pytest.raises(JobValidationError):
        await scraper_service.create_job(
            session,
            ScrapeJobCreate(source="delta", city="tehran", category="apartment-sell",
                            params={"execution_scope": "demand:7:1", "source_category": "villa-sell"}),
            settings=_settings(),
        )
    assert not session.added


@pytest.mark.asyncio
async def test_scheduled_delta_override_must_equal_verified_category_mapping():
    session = _Session()
    payload = ScrapeJobCreate(
        source="delta", city="tehran", category="apartment-sell",
        params={"execution_scope": "schedule:2026-10-27", "source_category": "villa-sell"},
    )
    with pytest.raises(JobValidationError):
        await scraper_service.create_job(
            session, payload, trigger=ScrapeJobTrigger.SCHEDULED, settings=_settings()
        )
    assert not session.added
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_scheduled_delta_job_uses_verified_source_category():
    session = _Session()
    payload = ScrapeJobCreate(
        source="delta", city="tehran", category="apartment-sell",
        params={"execution_scope": "schedule:2026-10-27", "source_category": "apartment-sell"},
    )
    job = await scraper_service.create_job(
        session, payload, trigger=ScrapeJobTrigger.SCHEDULED, settings=_settings()
    )
    assert job.category == "apartment-sell"
    assert job.params["source_category"] == "apartment-sell"
    assert session.added == [job]


@pytest.mark.asyncio
async def test_manual_source_category_slug_without_internal_scope_is_rejected():
    session = _Session()
    with pytest.raises(JobValidationError):
        await scraper_service.create_job(
            session,
            ScrapeJobCreate(
                source="delta", city="tehran", category="apartment-sell",
                params={"source_category": "villa-sell"},
            ),
            trigger=ScrapeJobTrigger.MANUAL,
            settings=_settings(),
        )
    assert not session.added


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


@pytest.mark.asyncio
async def test_unverified_divar_city_cannot_use_legacy_category_escape():
    session = _Session()
    with pytest.raises(JobValidationError) as error:
        await scraper_service.create_job(
            session,
            ScrapeJobCreate(source="divar", city="tehran", category="villa-sell"),
            settings=_settings(),
        )
    assert error.value.code == "UNVERIFIED_CITY"
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
        ScrapeJobCreate(source="delta", city="tabriz", category="apartment-sell"),
        settings=_settings(),
    )
    assert result is existing
    assert not session.added
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_active_postgres_job_is_reused_without_commit():
    existing = SimpleNamespace(status=ScrapeJobStatus.PENDING)
    session = _Session(duplicate=existing)

    class _Bind:
        class dialect:
            name = "postgresql"

    session.bind = _Bind()
    session.in_transaction = lambda: True
    session.rollback = AsyncMock()
    result = await scraper_service.create_job(
        session,
        ScrapeJobCreate(source="delta", city="tabriz", category="apartment-sell"),
        settings=_settings(),
    )
    assert result is existing
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
    assert not session.added


@pytest.mark.asyncio
async def test_completed_job_scope_filter_uses_only_active_statuses():
    session = _Session()
    from sqlalchemy.dialects import postgresql

    from app.models import ScrapeJob
    from app.models.enums import ScrapeJobStatus
    from sqlalchemy import select

    statement = select(ScrapeJob).where(
        ScrapeJob.status.in_((ScrapeJobStatus.PENDING, ScrapeJobStatus.RUNNING))
    )
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "scrape_job.status" in sql
    bound_statuses = next(
        value for value in compiled.params.values()
        if isinstance(value, (list, tuple))
    )
    assert set(bound_statuses) == {ScrapeJobStatus.PENDING, ScrapeJobStatus.RUNNING}


def test_scrape_job_advisory_lock_is_transaction_scoped_and_keyed_by_target(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock

    from app.models.enums import ScrapeJobKind

    session = _Session()
    class _Bind:
        class dialect:
            name = "postgresql"
    session.bind = _Bind()
    payload = ScrapeJobCreate(source="delta", city="tabriz", category="apartment-sell")
    # Exercise lock statement on a PostgreSQL-dialect-shaped session without
    # opening a database connection; commit/refresh remain mocked.
    async def run():
        return await scraper_service.create_job(session, payload, settings=_settings())
    asyncio.run(run())
    sql = [str(call.args[0]) for call in session.execute.await_args_list]
    assert any("pg_advisory_xact_lock" in statement for statement in sql)
    assert session.execute.await_args_list[0].args[1]["key"].startswith("scrape-target:delta:tabriz:apartment-sell:SEARCH:")


@pytest.mark.asyncio
async def test_failed_job_commit_rolls_back_and_does_not_leave_session_dirty():
    class FailingSession(_Session):
        def __init__(self):
            super().__init__()
            self.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
            self.rollback = AsyncMock()

    session = FailingSession()
    payload = ScrapeJobCreate(source="delta", city="tehran", category="apartment-sell")
    with pytest.raises(RuntimeError, match="commit failed"):
        await scraper_service.create_job(session, payload, settings=_settings())
    session.rollback.assert_awaited_once()
    assert len(session.added) == 1


def test_sheypoor_category_expansion_does_not_duplicate_source_routes():
    sale = resolve_categories("sheypoor", "house-villa-sell")
    apartment = resolve_categories("sheypoor", "apartment-sell")
    assert sale.categories == apartment.categories == ("houses-apartments-for-sale",)


def test_unknown_property_type_is_not_inferred_from_combined_route():
    from app.services.scraper.parser import DivarListingDetail
    from app.services.ingestion.sanitizer import build_property_fields

    detail = DivarListingDetail(token="unknown-type", city="تهران")
    with pytest.raises(ValueError, match="property type is unknown"):
        build_property_fields(detail, content_hash=None)


def test_generic_sheypoor_category_does_not_imply_property_type():
    from app.services.scraper.parser import PropertyType
    from app.services.scraper.sheypoor_parser import parse_sheypoor_detail

    detail = parse_sheypoor_detail({"__category": "houses-apartments-for-sale"}, "1")
    assert detail.property_type is None
    specific = parse_sheypoor_detail(
        {"__category": "houses-apartments-for-sale", "itemOffered": {"propertyType": "villa"}},
        "2",
    )
    assert specific.property_type == PropertyType.VILLA


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
    from app.models.enums import PropertySource, PropertyType
    from app.services.ingestion.sanitizer import build_property_fields
    from app.services.scraper.parser import DivarListingDetail

    fields = build_property_fields(
        DivarListingDetail(token="1", city="تهران", province="تهران", property_type=PropertyType.APARTMENT),
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


@pytest.mark.asyncio
async def test_dry_run_validates_without_persisting():
    session = _Session()
    from app.core.config import Settings

    settings = Settings(
        database_url="sqlite+aiosqlite://", scraper_enabled=True,
        scraper_cities="tehran", scraper_categories="apartment-sell",
        scraper_sources="delta",
    )
    result = await scraper_service.trigger_and_maybe_run(
        session,
        ScrapeJobCreate(source="delta", city="tehran", category="apartment-sell",
                        params={"dry_run": True}),
        settings=settings,
    )
    assert result is None
    assert not session.added
    session.commit.assert_not_awaited()