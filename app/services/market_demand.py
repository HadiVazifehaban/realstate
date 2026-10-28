"""Bounded, deduplicated collection for an explicitly selected empty city."""
from datetime import timedelta

from sqlalchemy import or_, select, text

from app.models import ScrapeJob
from app.models.base import utcnow
from app.models.enums import ScrapeJobStatus, ScrapeJobTrigger
from app.schemas.scraper import ScrapeJobCreate, ScrapeJobResponse
from app.services import scraper_service
from app.services.scraper.demand_locations import (
    demand_location,
    canonical_demand_city,
    source_city_targets,
    scope_sheypoor_results,
)

COOLDOWN = timedelta(minutes=10)
ACTIVE = (ScrapeJobStatus.PENDING, ScrapeJobStatus.RUNNING)
DEMAND_CATEGORIES = {
    'sheypoor': ('houses-apartments-for-sale', 'house-apartment-for-rent'),
    'divar': ('apartment-sell', 'apartment-rent'),
    'delta': ('apartment-sell', 'apartment-rent'),
}


async def ensure_city_inventory(session, city: str, settings) -> dict:
    located = demand_location(city)
    if located is None:
        return {"city": city, "status": "unsupported", "jobs": []}
    city = located["name"]
    if not settings.scraper_enabled:
        return {"city": city, "status": "disabled", "jobs": []}
    targets = {source: target for source, target in source_city_targets(located['id']).items()
               if source in settings.source_list}
    if not targets:
        return {"city": city, "status": "unsupported", "sources": {},
                'unsupported_sources': list(settings.source_list), "jobs": []}
    jobs = []
    source_states = {}
    for source, slug in targets.items():
        source_jobs = []
        for category in DEMAND_CATEGORIES[source]:
            generic_category = (
                "apartment-sell"
                if category.endswith("for-sale") or category == "apartment-sell"
                else "apartment-rent"
            )
            scope = f"demand:{located['id']}"
            bind = getattr(session, "bind", None)
            if bind is None and callable(getattr(session, "get_bind", None)):
                try:
                    bind = session.get_bind()
                except Exception:
                    bind = None
            dialect = getattr(getattr(bind, "dialect", None), "name", None)
            if dialect == "postgresql":
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                    {"key": f"market-demand:{located['id']}:{source}:{generic_category}"},
                )
            try:
                result = await session.execute(
                    select(ScrapeJob).where(
                        ScrapeJob.city == slug, ScrapeJob.source == source,
                        ScrapeJob.category == generic_category,
                        ScrapeJob.params["execution_scope"].as_string() == scope,
                        or_(ScrapeJob.status.in_(ACTIVE), ScrapeJob.created_at >= utcnow() - COOLDOWN),
                    ).order_by(ScrapeJob.created_at.desc()).limit(1)
                )
                job = result.scalar_one_or_none()
            except Exception:
                if dialect == "postgresql":
                    await session.rollback()
                raise
            if job is None:
                job = await scraper_service.trigger_with_trigger(
                    session,
                    ScrapeJobCreate(source=source, city=slug, category=generic_category,
                                    max_pages=1, fetch_phones=False,
                                    params={"source_category": category,
                                            "execution_scope": scope}),
                    trigger=ScrapeJobTrigger.MANUAL,
                    settings=settings,
                )
            elif dialect == "postgresql":
                await session.rollback()
            elif callable(getattr(session, "rollback", None)):
                await session.rollback()
            source_jobs.append(job)
            jobs.append(job)
        if any(job.status in ACTIVE for job in source_jobs):
            source_states[source] = 'collecting'
        elif any(job.status in (ScrapeJobStatus.FAILED, ScrapeJobStatus.CANCELLED)
                 or (job.items_failed and not job.items_new and not job.items_duplicate)
                 for job in source_jobs):
            source_states[source] = 'failed'
        else:
            source_states[source] = 'empty'
    if any(value == 'collecting' for value in source_states.values()):
        state = 'collecting'
    elif all(value == 'failed' for value in source_states.values()):
        state = 'failed'
    elif any(value == 'failed' for value in source_states.values()):
        state = 'partial'
    else:
        state = 'empty'
    return {"city": city, "city_id": located['id'], "status": state,
            'sources': source_states,
            'unsupported_sources': sorted(set(settings.source_list) - set(targets)),
            "jobs": [ScrapeJobResponse.from_job(job) for job in jobs]}


async def filter_source_summaries(source, city_slug, summaries):
    """Fail closed on cities for which a source result cannot be city-verified."""
    if source == 'sheypoor':
        return scope_sheypoor_results(summaries, city_slug)
    located = canonical_demand_city(city_slug)
    if located is None:
        return []
    if source == 'delta':
        # Delta's category route is city-scoped, but a detail page may omit its
        # address. Only allow the row if explicit detail-city evidence agrees;
        # never infer the listing's city from the request URL alone.
        from app.services.location_catalog import normalized_name, resolve_city

        expected = normalized_name(located['name'])
        accepted = []
        for summary in summaries:
            evidence = getattr(summary, "city", "") or ""
            resolved = resolve_city(evidence) if evidence else None
            if resolved and normalized_name(resolved['name']) == expected:
                accepted.append(summary)
        return accepted
    from app.services.location_catalog import normalized_name
    expected = normalized_name(located['name'])
    return [summary for summary in summaries if summary.city
            and normalized_name(summary.city) == expected]


async def city_has_inventory(session, located):
    """Check stored inventory in the selected composite catalog location."""
    from sqlalchemy import select
    from app.models import Property
    from app.services.location_catalog import location_condition
    result = await session.execute(
        select(Property.id).where(
            location_condition(Property, city_ids=[located['id']])
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None