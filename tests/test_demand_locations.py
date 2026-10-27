"""Offline coverage checks against the checked-in source-owned catalog."""
from app.services.scraper.demand_locations import (
    demand_coverage, demand_location, scope_sheypoor_results, source_locations,
)
from app.services.scraper.parser import DivarListingDetail
from app.services.ingestion.sanitizer import build_property_fields
from types import SimpleNamespace


def test_all_catalog_rows_have_explicit_coverage():
    rows = demand_coverage()
    assert len(rows) == 344
    assert sum(bool(row['slug']) for row in rows) == 330
    assert len({row['id'] for row in rows}) == len(rows)
    source_slugs = {row['slug'] for row in source_locations()}
    assert all(row['slug'] in source_slugs for row in rows if row['slug'])


def test_ambiguous_names_require_composite_id():
    assert demand_location('اردکان') is None
    assert demand_location('16:16')['slug'] == 'fars-ardakan'
    assert demand_location('31:3')['slug'] == 'yazd-ardakan'


def test_incorrect_catalog_province_never_matches_another_province():
    assert demand_location('12:2')['slug'] is None  # IranShahr in Khuzestan
    assert demand_location('26:3')['slug'] is None  # Dezful in Lorestan


def test_source_spelling_variant_and_recommendation_scope():
    mapped = demand_location('6:2')
    assert mapped['slug'] == 'bandar-dayyer'
    rows = [SimpleNamespace(city=c) for c in ('بندر دیر', 'دیر', 'تهران', '')]
    assert scope_sheypoor_results(rows, mapped['slug']) == rows[:2]


def test_same_named_city_preserves_province_in_ingestion():
    detail = DivarListingDetail(token='test', city='اردکان', province='فارس')
    fields = build_property_fields(detail, content_hash=None)
    assert fields['province'] == 'فارس'
    assert fields['city'] == 'اردکان'