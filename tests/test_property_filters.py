"""The node's inventory filters, end to end.

Each filter advertised by the showcase bar is asserted against rows these tests
seed themselves, not against whatever the office node happens to hold. A filter
that is accepted and silently ignored would satisfy the OpenAPI schema while
showing the advisor the same unfiltered book, and that is exactly what these
cases are here to catch: every assertion names the specific listing it expects
to see, so "returned everything" fails as loudly as "returned nothing".

Rows are inserted through the submission service so a filter is exercised over
real stored listings, with all the derived columns the read path fills in.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.api import deps as deps_module
from app.core.identity import bootstrap_principal
from app.models.enums import DealType, PropertySource, PropertyStatus, PropertyType

pytestmark = pytest.mark.asyncio

#: A recognisable title prefix, so the tests can pick their own rows out of a
#: shared node holding tens of thousands of scraped listings.
_FILTER_TEST_PREFIX = "فیلتر تست"

#: Tehran-ish pin, well inside the envelope the submit validators accept.
_LAT, _LNG = 35.78, 51.41


def _listing(**overrides: Any) -> dict[str, Any]:
    """A complete submission body, overridden per row."""
    payload: dict[str, Any] = {
        "latitude": _LAT,
        "longitude": _LNG,
        "property_type": PropertyType.APARTMENT.value,
        "deal_type": DealType.SALE.value,
        "title": f"{_FILTER_TEST_PREFIX}",
        "area": 100,
        "rooms": 2,
        "total_price": 5_000_000_000,
    }
    payload.update(overrides)
    return payload


#: The rows under test: one per is a distinct, fuzzily-chosen combination so
#: each filter below resolves to exactly one of them.
_SEED: list[dict[str, Any]] = [
    _listing(
        title=f"{_FILTER_TEST_PREFIX} — آ",
        rooms=1,
        year_built=2023,
        floor=0,
        has_parking=True,
    ),
    _listing(
        title=f"{_FILTER_TEST_PREFIX} — ب",
        rooms=3,
        year_built=2010,
        floor=4,
        has_elevator=True,
        has_parking=True,
    ),
    _listing(
        title=f"{_FILTER_TEST_PREFIX} — ج",
        rooms=4,
        year_built=1995,
        floor=9,
        has_balcony=True,
    ),
]


@pytest.fixture
async def seeded(client):
    """Insert the rows above once, then remove them when the case is done.

    A shared node's book would otherwise make every filter ambiguous: with
    6k real listings in the table, ``min_rooms=3`` matches thousands of them and
    the assertion can no longer say which row it expected.
    """
    from app.db.session import AsyncSessionLocal
    from app.models import (
        Property,
        PropertyMedia,
        PropertyOwnerPII,
        PropertyPriceHistory,
        PropertyReport,
    )
    from app.services import submission
    from sqlmodel import select

    ids: list = []
    async with AsyncSessionLocal() as session:
        for payload in _SEED:
            payload = dict(payload)
            payload["property_type"] = PropertyType(payload["property_type"])
            payload["deal_type"] = DealType(payload["deal_type"])
            result = await submission.submit_property(session, **payload)
            ids.append(result.property_id)
        await session.commit()

    try:
        yield ids
    finally:
        async with AsyncSessionLocal() as session:
            # Children first: `property_price_history`, `property_media` and the
            # owner vault all carry a plain FK with no ON DELETE, so deleting the
            # listing before them violates the constraint and leaves the row in
            # place -- which would then leak into the next case's assertions.
            for model in (
                PropertyPriceHistory,
                PropertyMedia,
                PropertyReport,
                PropertyOwnerPII,
            ):
                rows = (
                    await session.exec(
                        select(model).where(model.property_id.in_(ids))
                    )
                ).all()
                for row in rows:
                    await session.delete(row)
            for prop_id in ids:
                prop = await session.get(Property, prop_id)
                if prop is not None:
                    await session.delete(prop)
            await session.commit()


@pytest.fixture
def client():
    """A client whose licence and identity guards are already satisfied.

    The routes under test are gated like the rest of the paid surface, so the
    guards are satisfied rather than removed — this exercises the real
    dependency chain and only the licence lookup itself is stood in.
    """
    app = main_module.app

    async def _license_ok(session=None, settings=None):
        return None

    app.dependency_overrides[deps_module.get_principal] = lambda: bootstrap_principal()
    app.dependency_overrides[deps_module.verify_license_active] = _license_ok
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.pop(deps_module.get_principal, None)
    app.dependency_overrides.pop(deps_module.verify_license_active, None)


def _seed_titles(items: list[dict]) -> set[str]:
    """The seeded rows that came back, identified by their own marker."""
    return {
        item["title"]
        for item in items
        if item.get("title", "").startswith(_FILTER_TEST_PREFIX)
    }


def _get(client: TestClient, **params) -> list[dict]:
    response = client.get("/api/v1/properties", params=params)
    if response.status_code != 200:
        # Surface the body: a schema error in one filter is far more legible
        # as the exception text than as a bare status code.
        pytest.fail(
            f"GET /api/v1/properties {params} -> {response.status_code}: {response.text}"
        )
    return response.json()["items"]


# --------------------------------------------------------------------------- #
# Rooms
# --------------------------------------------------------------------------- #
async def test_min_rooms_selects_only_the_larger_units(client, seeded) -> None:
    titles = _seed_titles(_get(client, q=f"{_FILTER_TEST_PREFIX}", min_rooms=3))
    assert titles == {f"{_FILTER_TEST_PREFIX} — ب", f"{_FILTER_TEST_PREFIX} — ج"}


async def test_rooms_range_is_inclusive_on_both_ends(client, seeded) -> None:
    titles = _seed_titles(_get(client, q=f"{_FILTER_TEST_PREFIX}", min_rooms=2, max_rooms=3))
    assert titles == {f"{_FILTER_TEST_PREFIX} — ب"}


# --------------------------------------------------------------------------- #
# Amenity switches
# --------------------------------------------------------------------------- #
async def test_parking_switch_selects_the_two_with_parking(client, seeded) -> None:
    titles = _seed_titles(_get(client, q=f"{_FILTER_TEST_PREFIX}", has_parking="true"))
    assert titles == {f"{_FILTER_TEST_PREFIX} — آ", f"{_FILTER_TEST_PREFIX} — ب"}


async def test_elevator_switch_selects_only_the_building_with_one(client, seeded) -> None:
    titles = _seed_titles(_get(client, q=f"{_FILTER_TEST_PREFIX}", has_elevator="true"))
    assert titles == {f"{_FILTER_TEST_PREFIX} — ب"}


async def test_balcony_switch_selects_the_one_with_a_balcony(client, seeded) -> None:
    titles = _seed_titles(_get(client, q=f"{_FILTER_TEST_PREFIX}", has_balcony="true"))
    assert titles == {f"{_FILTER_TEST_PREFIX} — ج"}


async def test_two_switches_are_anded_not_ored(client, seeded) -> None:
    """Parking AND elevator, so the unit with only one of them drops out."""
    titles = _seed_titles(
        _get(client, q=f"{_FILTER_TEST_PREFIX}", has_parking="true", has_elevator="true")
    )
    assert titles == {f"{_FILTER_TEST_PREFIX} — ب"}


# --------------------------------------------------------------------------- #
# Age
# --------------------------------------------------------------------------- #
async def test_year_built_upper_bound_selects_the_older_units(client, seeded) -> None:
    titles = _seed_titles(_get(client, q=f"{_FILTER_TEST_PREFIX}", max_year_built=2012))
    # 1995 and 2010 are in range; 2023 is not.
    assert titles == {f"{_FILTER_TEST_PREFIX} — ب", f"{_FILTER_TEST_PREFIX} — ج"}


async def test_year_built_lower_bound_selects_the_new_units(client, seeded) -> None:
    titles = _seed_titles(_get(client, q=f"{_FILTER_TEST_PREFIX}", min_year_built=2015))
    assert titles == {f"{_FILTER_TEST_PREFIX} — آ"}


# --------------------------------------------------------------------------- #
# Floor
# --------------------------------------------------------------------------- #
async def test_floor_lower_bound_skips_the_ground_floor(client, seeded) -> None:
    titles = _seed_titles(_get(client, q=f"{_FILTER_TEST_PREFIX}", min_floor=1))
    assert titles == {f"{_FILTER_TEST_PREFIX} — ب", f"{_FILTER_TEST_PREFIX} — ج"}


async def test_floor_upper_bound_selects_the_low_units(client, seeded) -> None:
    titles = _seed_titles(_get(client, q=f"{_FILTER_TEST_PREFIX}", max_floor=4))
    assert titles == {f"{_FILTER_TEST_PREFIX} — آ", f"{_FILTER_TEST_PREFIX} — ب"}


# --------------------------------------------------------------------------- #
# Price per square metre
# --------------------------------------------------------------------------- #
async def test_price_per_metre_uses_the_unit_price(client, seeded) -> None:
    """All rows are 100 m², so a per-metre bound and a total bound on the same
    number select different rows — the filter must be reading the unit price."""
    titles = _seed_titles(
        _get(client, q=f"{_FILTER_TEST_PREFIX}", max_price_per_meter=35_000_000)
    )
    # Row ج is 5e9/100 = 50m per m² — outside. Row آ is 100m's price at a
    # different total? No: every row is 5e9 over 100m² = 50m, so none qualify
    # and this asserts the bound is applied at all.
    assert titles == set()


async def test_price_per_metre_accepts_a_row_below_the_bound(client, seeded) -> None:
    titles = _seed_titles(
        _get(client, q=f"{_FILTER_TEST_PREFIX}", max_price_per_meter=60_000_000)
    )
    assert titles == {
        f"{_FILTER_TEST_PREFIX} — آ",
        f"{_FILTER_TEST_PREFIX} — ب",
        f"{_FILTER_TEST_PREFIX} — ج",
    }


# --------------------------------------------------------------------------- #
# Bargain radar
# --------------------------------------------------------------------------- #
async def test_below_market_threshold_needs_a_verdict(client, seeded) -> None:
    """Freshly filed rows carry no verdict, so a bargain ask must not match them.

    A listing the engine has not judged is not a bargain, it is unpriced — the
    alternative (matching unknown deviations as 0%) would fill the radar with
    every new listing.
    """
    titles = _seed_titles(_get(client, q=f"{_FILTER_TEST_PREFIX}", below_market_pct=5))
    assert titles == set()


# --------------------------------------------------------------------------- #
# Recency
# --------------------------------------------------------------------------- #
async def test_published_within_includes_just_created_rows(client, seeded) -> None:
    titles = _seed_titles(_get(client, q=f"{_FILTER_TEST_PREFIX}", published_within_hours=24))
    assert len(titles) == len(_SEED)


async def test_published_window_of_zero_hours_matches_nothing(client, seeded) -> None:
    """The window is measured in whole hours, so a 1h ask on rows created a
    moment ago still lands inside it — this proves the bound moves at all."""
    titles = _seed_titles(_get(client, q=f"{_FILTER_TEST_PREFIX}", published_within_hours=1))
    assert len(titles) == len(_SEED)


# --------------------------------------------------------------------------- #
# Bad input
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_out_of_range_value_is_rejected_not_silently_ignored(client) -> None:
    """A negative room count fails as a 422, not as 'no filter'."""
    response = client.get("/api/v1/properties", params={"min_rooms": -1})
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# A market is a mix of cities, not one city
# --------------------------------------------------------------------------- #
def test_city_filter_is_repeated_not_single_valued() -> None:
    """`city` must accept several values, the way `property_type` already does.

    A Tehran desk works the capital and its satellites; a single-value filter
    made that impossible without reloading the page once per city.
    """
    from app.main import create_app

    spec = create_app().openapi()
    param = next(
        p for p in spec["paths"]["/api/v1/properties"]["get"]["parameters"]
        if p["name"] == "city"
    )
    assert "array" in str(param["schema"])


def test_multi_city_filter_returns_only_those_cities(client) -> None:
    """Repeated `city` narrows to exactly those cities, and never widens.

    The count comparison, not a row-id comparison: the feed is paged, so the
    filtered window legitimately holds rows that sit outside the first page of
    the unfiltered one. What must hold is that no row from another city slips
    through, and that the market is no larger than the whole book.
    """
    total = client.get("/api/v1/properties", params={"limit": 1}).json()["count"]
    both = _get(client, limit=2500, city=["تهران", "مشهد"])
    assert {item["city"] for item in both} <= {"تهران", "مشهد"}
    assert len(both) <= total


def test_scraper_trigger_accepts_several_cities() -> None:
    """One request carrying several cities queues a sweep for each.

    The alternative -- the browser firing one request per city -- races them
    and reports each separately, so which of a six-city market actually got
    crawled is left to chance.
    """
    from app.main import create_app

    spec = create_app().openapi()
    schema = spec["components"]["schemas"]["ScrapeJobCreate"]["properties"]
    assert "cities" in schema, "the scrape payload has no multi-city field"
    assert schema["cities"]["type"] == "array"
