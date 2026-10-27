"""Source-owned locations matched by province AND city, never GIS numeric IDs."""
import json
from functools import lru_cache
from pathlib import Path

from app.services.location_catalog import catalog, normalized_name

SOURCE_PATH = Path(__file__).with_name('data') / 'sheypoor_locations.json'
PROVINCE_ALIASES = {'چهارمحال بختیاری': 'چهارمحال و بختیاری'}
CITY_ALIASES = {'دیر': 'بندر دیر', 'کنگان': 'بندر کنگان', 'گناوه': 'بندر گناوه',
                'قائن': 'قاین', 'ری': 'شهر ری'}


@lru_cache(maxsize=1)
def source_locations():
    return json.loads(SOURCE_PATH.read_text(encoding='utf-8'))['cities']


@lru_cache(maxsize=1)
def demand_coverage():
    rows = []
    for province in catalog()['provinces']:
        province_name = PROVINCE_ALIASES.get(province['name'], province['name'])
        for city in province['cities']:
            name = CITY_ALIASES.get(city['name'], city['name'])
            candidates = [row for row in source_locations()
                          if normalized_name(row['province']) == normalized_name(province_name)
                          and normalized_name(row['name']) == normalized_name(name)]
            mapping = candidates[0] if len(candidates) == 1 else None
            rows.append({**city, 'status': 'supported' if mapping else 'needs_mapping',
                         'source': 'sheypoor', 'slug': mapping['slug'] if mapping else None,
                         'source_city_id': mapping['source_city_id'] if mapping else None,
                         'source_name': mapping['name'] if mapping else None})
    return rows


def demand_location(city):
    exact = [row for row in demand_coverage() if row['id'] == city]
    if exact:
        return exact[0]
    matches = [row for row in demand_coverage()
               if normalized_name(row['name']) == normalized_name(city)]
    return matches[0] if len(matches) == 1 else None


def canonical_demand_city(slug):
    rows = [row for row in demand_coverage() if row['slug'] == slug]
    return rows[0] if len(rows) == 1 else None


def source_city_targets(city):
    """Return independently registered, source-specific targets for a city.

    GIS IDs are never forwarded to portal APIs. Divar IDs are marked
    unverified in its registry and are therefore deliberately excluded from
    automatic collection until a live refresh confirms them.
    """
    from app.services.scraper.cities import get_city
    from app.services.scraper.delta_taxonomy import DELTA_CITIES

    located = demand_location(city)
    if located is None:
        return {}
    targets = {}
    if located['slug']:
        targets['sheypoor'] = located['slug']
    # A portal slug may equal Sheypoor's slug by coincidence; require the
    # separately curated cross-source mapping, then validate against its own
    # registry. Delta numeric IDs are not used in its URL routing.
    try:
        divar = get_city(located['name'])
    except ValueError:
        divar = None
    if divar and divar.is_verified:
        targets['divar'] = divar.slug
    # Delta's registry is authoritative for the accepted URL segment. Its
    # city labels are Persian in the catalog; these crosswalk aliases are
    # explicit to avoid guessing transliterations from unrelated sources.
    delta_aliases = {
        'تهران': 'tehran', 'مشهد': 'mashhad', 'اصفهان': 'isfahan',
        'شیراز': 'shiraz', 'تبریز': 'tabriz', 'کرمانشاه': 'kermanshah',
        'ارومیه': 'urmia', 'رشت': 'rasht',
    }
    delta_slug = delta_aliases.get(located['name'])
    if delta_slug in DELTA_CITIES:
        targets['delta'] = delta_slug
    return targets


def scope_sheypoor_results(rows, slug):
    mappings = [row for row in demand_coverage() if row['slug'] == slug]
    if not mappings:
        return rows
    names = {normalized_name(row[key]) for row in mappings for key in ('name', 'source_name')}
    return [row for row in rows if normalized_name(row.city) in names]


# Compatibility for callers inspecting unambiguous legacy names.
SHEYPOOR_CITY_SLUGS = {row['name']: row['slug'] for row in demand_coverage()
                      if row['slug'] and demand_location(row['name']) is not None}