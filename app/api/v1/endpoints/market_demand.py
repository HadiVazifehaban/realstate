"""Reader-accessible demand endpoint, without exposing operator scrape controls."""
from fastapi import APIRouter
from pydantic import BaseModel, Field, constr

from app.api.deps import LicenseGuard, SessionDep, SettingsDep
from app.services.market_demand import ensure_city_inventory, city_has_inventory
from app.services.scraper.demand_locations import demand_coverage, demand_location

router = APIRouter()


@router.get('/inventory-coverage')
async def inventory_coverage(_license: LicenseGuard):
    rows = demand_coverage()
    return {'items': rows, 'total': len(rows),
            'supported': sum(row['status'] == 'supported' for row in rows)}


@router.get('/inventory-sources')
async def inventory_sources(_license: LicenseGuard):
    from app.services.scraper.registry import source_keys
    from app.services.scraper.demand_locations import source_city_targets
    return {'sources': list(source_keys()),
            'cities': {row['id']: source_city_targets(row['id']) for row in demand_coverage()}}


class MarketDemandRequest(BaseModel):
    cities: list[constr(strip_whitespace=True, min_length=1, max_length=64)] = Field(min_length=1, max_length=400)


@router.post("/ensure-inventory")
async def ensure_inventory(payload: MarketDemandRequest, session: SessionDep,
                           settings: SettingsDep, _license: LicenseGuard):
    results = []
    for city in dict.fromkeys(c.strip() for c in payload.cities if c.strip()):
        try:
            located = demand_location(city)
            if located is None:
                results.append({'city': city, 'status': 'unsupported', 'sources': {}, 'jobs': []})
                continue
            # Keep an inventory check separate from job creation so one existing
            # source row does not mask missing inventories in the other portals.
            by_id = city == located['id']
            if await city_has_inventory(session, located):
                results.append({'city': located['name'], 'city_id': located['id'],
                                'status': 'available', 'sources': {}, 'jobs': []})
                continue
            await session.rollback()  # release the read transaction before job locks/commits
            results.append(await ensure_city_inventory(session, city, settings))
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    return {"items": results}