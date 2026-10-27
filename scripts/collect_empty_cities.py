"""Collect empty catalog cities sequentially; dry-run unless --execute is given.

Run from the project root: python -m scripts.collect_empty_cities [--execute]
Uses the application's existing license gate; never runs migrations.
"""
import argparse
import asyncio
import json

from app.services.scraper.demand_locations import demand_coverage


async def collect():
    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal
    from app.services import scraper_service
    from app.services.market_demand import ensure_city_inventory
    from app.services.scraper_scheduler import _license_usable
    from sqlalchemy import text

    settings = get_settings()
    if not settings.scraper_enabled or 'sheypoor' not in settings.source_list:
        raise SystemExit('Enable scraper and Sheypoor before executing.')
    async with AsyncSessionLocal() as session:
        if session.bind.dialect.name == 'postgresql':
            column = await session.execute(text(
                "SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema() "
                "AND table_name = 'property' AND column_name = 'agency_id'"
            ))
            if column.scalar_one_or_none() is None:
                raise SystemExit('Schema incompatible: property.agency_id missing. '
                                 'No jobs queued. Review migration before execution.')
    # Disable background launch only for this dedicated CLI process. Await each
    # persisted job before queuing another city; restarting safely reuses jobs.
    scraper_service.launch_job_background = lambda *_args: None
    for city in demand_coverage():
        if not city['slug']:
            print(json.dumps({'city_id': city['id'], 'city': city['name'],
                              'status': 'unsupported'}, ensure_ascii=False), flush=True)
            continue
        async with AsyncSessionLocal() as session:
            if not await _license_usable(session, settings):
                raise SystemExit('Active scraping license required.')
            answer = await ensure_city_inventory(session, city['id'], settings)
            await session.commit()
        for job in answer['jobs']:
            await scraper_service.execute_job(job.id, settings=settings)
        async with AsyncSessionLocal() as session:
            final_jobs = [await scraper_service.get_job(session, job.id) for job in answer['jobs']]
            answer['jobs'] = [scraper_service.ScrapeJobResponse.from_job(job).model_dump(mode='json')
                              for job in final_jobs if job is not None]
            if answer['status'] == 'collecting':
                answer['status'] = 'processed'
        print(json.dumps(answer, default=str, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute:
        asyncio.run(collect())
    else:
        rows = demand_coverage()
        print(json.dumps({'total': len(rows), 'supported': sum(bool(r['slug']) for r in rows),
                          'items': rows}, ensure_ascii=False, indent=2))