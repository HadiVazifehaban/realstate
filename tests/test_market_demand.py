"""Offline tests: no live jobs, DB writes or portal traffic."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models import ScrapeJob
from app.models.enums import ScrapeJobStatus
from app.services import market_demand
from app.services.market_demand import city_has_inventory
from app.services.scraper.demand_locations import source_city_targets


def result(value):
    return SimpleNamespace(scalar_one_or_none=lambda: value)


def test_recommendations_are_not_assigned_to_requested_city():
    from app.services.scraper.demand_locations import scope_sheypoor_results
    rows = [SimpleNamespace(city=city) for city in ('مراغه', 'تهران', '')]
    assert scope_sheypoor_results(rows, 'maragheh') == rows[:1]


@pytest.mark.asyncio
async def test_existing_inventory_never_starts_job(monkeypatch):
    launch = AsyncMock()
    monkeypatch.setattr(market_demand.scraper_service, 'trigger_and_maybe_run', launch)
    located = market_demand.demand_location('مراغه')
    session = SimpleNamespace(execute=AsyncMock(side_effect=[result('property-id')]))
    assert await city_has_inventory(session, located)
    launch.assert_not_called()


@pytest.mark.asyncio
async def test_empty_maragheh_uses_source_slug_and_bounded_job(monkeypatch):
    job = ScrapeJob(city='maragheh', source='sheypoor', category='real-estate')
    launch = AsyncMock(return_value=job)
    monkeypatch.setattr(market_demand.scraper_service, 'trigger_and_maybe_run', launch)
    session = SimpleNamespace(execute=AsyncMock(side_effect=[result(None), None, result(None), None]))
    answer = await market_demand.ensure_city_inventory(
        session, 'مراغه', SimpleNamespace(scraper_enabled=True, source_list=('sheypoor',)))
    assert answer['status'] == 'collecting'
    assert launch.await_count == 2
    payload = launch.call_args.args[1]
    assert (payload.city, payload.source, payload.max_pages, payload.fetch_phones) == (
        'maragheh', 'sheypoor', 1, False)
    from app.services.scraper.sheypoor_taxonomy import resolve_slug
    assert resolve_slug(payload.category) is not None


def test_platform_coverage_does_not_guess_unverified_sources():
    maragheh = source_city_targets('مراغه')
    assert maragheh == {'sheypoor': 'maragheh'}
    tehran = source_city_targets('تهران')
    assert tehran['sheypoor'] == 'tehran'
    assert tehran['delta'] == 'tehran'
    # Divar catalog IDs are explicitly unverified and must not auto-crawl.
    assert 'divar' not in tehran


@pytest.mark.asyncio
async def test_source_scoping_fails_closed_for_delta_neighbour_cities():
    from app.services.market_demand import filter_source_summaries
    rows = [SimpleNamespace(city='دزفول'), SimpleNamespace(city='اندیمشک'),
            SimpleNamespace(city='')]
    assert await filter_source_summaries('delta', 'andimeshk', rows) == rows


@pytest.mark.asyncio
@pytest.mark.parametrize('status,expected', [
    (ScrapeJobStatus.RUNNING, 'collecting'),
    (ScrapeJobStatus.FAILED, 'failed'),
    (ScrapeJobStatus.COMPLETED, 'empty'),
])
async def test_active_and_recent_jobs_are_reused(monkeypatch, status, expected):
    launch = AsyncMock()
    monkeypatch.setattr(market_demand.scraper_service, 'trigger_and_maybe_run', launch)
    job = ScrapeJob(city='maragheh', source='sheypoor', status=status)
    session = SimpleNamespace(execute=AsyncMock(side_effect=[result(job), result(job)]))
    answer = await market_demand.ensure_city_inventory(
        session, 'مراغه', SimpleNamespace(scraper_enabled=True, source_list=('sheypoor',)))
    assert answer['status'] == expected
    launch.assert_not_called()


@pytest.mark.asyncio
async def test_empty_city_queues_each_configured_supported_source(monkeypatch):
    jobs = []
    async def make_job(_session, payload, **kwargs):
        job = ScrapeJob(city=payload.city, source=payload.source, category=payload.category,
                        status=ScrapeJobStatus.PENDING)
        jobs.append(payload)
        return job
    monkeypatch.setattr(market_demand.scraper_service, 'trigger_and_maybe_run', make_job)
    responses = []
    for _ in range(4):  # two Sheypoor categories, two Delta categories
        responses.extend((result(None), None))
    session = SimpleNamespace(execute=AsyncMock(side_effect=responses))
    answer = await market_demand.ensure_city_inventory(
        session, 'تهران', SimpleNamespace(scraper_enabled=True,
                                          source_list=('sheypoor', 'delta', 'divar')))
    assert answer['sources'] == {'sheypoor': 'collecting', 'delta': 'collecting'}
    assert answer['unsupported_sources'] == ['divar']
    assert {(job.source, job.city) for job in jobs} == {
        ('sheypoor', 'tehran'), ('delta', 'tehran')}
    assert len(jobs) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize('city,enabled,sources,expected', [
    ('مراغه', False, ('sheypoor',), 'disabled'),
    ('مراغه', True, ('divar',), 'unsupported'),
    ('صلوات آباد', True, ('sheypoor',), 'unsupported'),
    ('invalid', True, ('sheypoor',), 'unsupported'),
])
async def test_disabled_and_unmapped_cities_do_not_queue(monkeypatch, city, enabled, sources, expected):
    launch = AsyncMock()
    monkeypatch.setattr(market_demand.scraper_service, 'trigger_and_maybe_run', launch)
    session = SimpleNamespace(execute=AsyncMock(side_effect=[result(None)]))
    answer = await market_demand.ensure_city_inventory(
        session, city, SimpleNamespace(scraper_enabled=enabled, source_list=sources))
    assert answer['status'] == expected
    launch.assert_not_called()


@pytest.mark.asyncio
async def test_existing_inventory_does_not_hide_missing_portal_inventory(monkeypatch):
    calls = []
    async def launch(_session, payload, **kwargs):
        job = ScrapeJob(city=payload.city, source=payload.source, category=payload.category,
                        status=ScrapeJobStatus.PENDING)
        calls.append(payload)
        return job
    monkeypatch.setattr(market_demand.scraper_service, 'trigger_and_maybe_run', launch)
    session = SimpleNamespace(execute=AsyncMock(side_effect=[result(None), None, result(None), None]))
    answer = await market_demand.ensure_city_inventory(
        session, 'مراغه', SimpleNamespace(scraper_enabled=True, source_list=('sheypoor',)))
    assert answer['status'] == 'collecting'
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_background_jobs_respect_process_concurrency_limit(monkeypatch):
    import asyncio
    active = 0
    peak = 0
    release = asyncio.Event()

    async def execute(*args):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await release.wait()
        active -= 1

    service = market_demand.scraper_service
    monkeypatch.setattr(service, 'execute_job', execute)
    monkeypatch.setattr(service, '_execution_slots', asyncio.Semaphore(2))
    for _ in range(8):
        service.launch_job_background(None, {})
    tasks = list(service._background_tasks)
    try:
        await asyncio.sleep(0)
        assert peak == 2
    finally:
        release.set()
        await asyncio.gather(*tasks)
    assert active == 0