"""Market map tests: the neighbourhood aggregation behind `/dashboard/avm`.

The shaping rules are asserted without a database; the grouped PostGIS query is
exercised against a real node when one is reachable.

What carries risk for a broker reading the map:

* a median must describe listings that actually hold that price, so an unpriced
  file never contributes a zero;
* the bargain share is taken over *every* file, not over the priced subset,
  otherwise a neighbourhood with one priced file reads as a pure bargain zone;
* a row with no files is dropped rather than drawn as a zero bubble at the
  centre of the neighbourhood.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, text

from app.models import Property
from app.models.enums import DealType, PropertySource, PropertyStatus, ValuationStatus
from app.services import market

#: Row layout of the grouped query, kept in one place so a column added to the
#: select cannot silently shift the assertions below.
ROW = (
    "تهران",  # city
    "محلهٔ آزمون",  # neighborhood
    12,  # files (priced)
    20,  # all_files
    210_000_000,  # median ppm
    12_000_000_000,  # median total
    None,  # median deposit
    None,  # median rent
    88.5,  # median area
    3,  # bargains
    -12.5,  # median deviation
    35.7123,  # latitude
    51.4123,  # longitude
)


def test_a_neighbourhood_row_is_shaped_for_the_map() -> None:
    (stat,) = market._rows_to_stats([ROW])

    assert stat.neighborhood == "محلهٔ آزمون"
    assert stat.files == 12
    assert stat.all_files == 20
    assert stat.median_price_per_meter == 210_000_000
    assert stat.median_area == 88.5
    assert stat.latitude == pytest.approx(35.7123)
    # 3 of 20 files, not 3 of the 12 priced ones.
    assert stat.bargain_share == pytest.approx(0.15)


def test_prices_are_rounded_to_whole_toman() -> None:
    """`percentile_cont` answers with a float even for a BIGINT column."""
    row = list(ROW)
    row[4] = 210_000_000.4
    (stat,) = market._rows_to_stats([tuple(row)])

    assert stat.median_price_per_meter == 210_000_000
    assert isinstance(stat.median_price_per_meter, int)


def test_an_unpriced_neighbourhood_is_not_drawn() -> None:
    row = list(ROW)
    row[2] = 0
    assert market._rows_to_stats([tuple(row)]) == []


def test_a_blank_neighbourhood_name_is_dropped() -> None:
    """The node stores `''` for listings whose portal never named a mahalle."""
    row = list(ROW)
    row[1] = ""
    assert market._rows_to_stats([tuple(row)]) == []


def test_a_neighbourhood_with_no_bargains_reports_zero() -> None:
    row = list(ROW)
    row[9] = None
    (stat,) = market._rows_to_stats([tuple(row)])

    assert stat.bargain_share == 0.0


def test_rent_priced_by_deposit_rather_than_price_per_meter() -> None:
    """A rent has no price per metre; requiring one would drop every rent."""
    sale = market._priced_condition([DealType.SALE])
    rent = market._priced_condition([DealType.RENT])
    full_mortgage = market._priced_condition([DealType.FULL_MORTGAGE])

    assert "price_per_meter" in str(sale)
    assert "price_per_meter" not in str(rent)
    assert "deposit_amount" in str(rent)
    # FULL_MORTGAGE is a rent with no monthly rent, so it rides with RENT.
    assert "deposit_amount" in str(full_mortgage)


# --------------------------------------------------------------------------- #
# Integration -- the grouped query against a real node
# --------------------------------------------------------------------------- #
@pytest.fixture()
async def db_ready() -> None:
    from app.db.session import engine

    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT to_regclass('public.property') IS NOT NULL "
                    "AND EXISTS (SELECT 1 FROM pg_extension WHERE extname='postgis')"
                )
            )
            if not bool(result.scalar()):
                raise RuntimeError("schema missing")
    except Exception:  # noqa: BLE001
        pytest.skip("PostgreSQL/PostGIS not available")


async def test_grouped_query_medians_one_neighbourhood(db_ready: None) -> None:
    from app.db.session import AsyncSessionLocal

    # A name no real listing can collide with, so the assertions hold on a node
    # that already carries thousands of scraped files.
    label = f"محلهٔ آزمون {uuid.uuid4().hex[:8]}"
    session = AsyncSessionLocal()

    prices = [100_000_000, 200_000_000, 600_000_000]
    props = [
        Property(
            title="واحد آزمون",
            location="SRID=4326;POINT(51.4100 35.7100)",
            latitude=35.71,
            longitude=51.41,
            city="تهران",
            neighborhood=label,
            deal_type=DealType.SALE,
            status=PropertyStatus.ACTIVE,
            source=PropertySource.INTERNAL_AGENCY,
            area=100.0,
            price_per_meter=price,
            total_price=price * 100,
            valuation_status=(
                ValuationStatus.BARGAIN if index == 0 else ValuationStatus.FAIR
            ),
        )
        for index, price in enumerate(prices)
    ]
    # Unpriced file in the same neighbourhood: counted for coverage only.
    props.append(
        Property(
            title="واحد بی‌قیمت",
            location="SRID=4326;POINT(51.4100 35.7100)",
            latitude=35.71,
            longitude=51.41,
            city="تهران",
            neighborhood=label,
            deal_type=DealType.SALE,
            status=PropertyStatus.ACTIVE,
            source=PropertySource.INTERNAL_AGENCY,
        )
    )

    session.add_all(props)
    await session.commit()

    try:
        overview = await market.neighbourhood_market(
            session, city="تهران", deal_types=[DealType.SALE], min_files=1, limit=500
        )
        stat = next(
            (item for item in overview.neighbourhoods if item.neighborhood == label),
            None,
        )
        assert stat is not None, "the seeded neighbourhood is missing from the map"
        assert stat.files == 3, "the unpriced file must not be counted as priced"
        assert stat.all_files == 4
        assert stat.median_price_per_meter == 200_000_000
        assert stat.median_total_price == 20_000_000_000
        assert stat.bargain_share == pytest.approx(0.25)
        assert stat.latitude == pytest.approx(35.71, abs=1e-6)

        # The city totals cover the whole node, not just this bubble.
        assert overview.total_files >= 4
        assert overview.median_price_per_meter is not None
    finally:
        await session.execute(
            delete(Property).where(Property.neighborhood == label)
        )
        await session.commit()
        await session.close()
