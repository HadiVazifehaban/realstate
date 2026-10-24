"""Phase 3b: deterministic valuation engine + geo helpers.

The estimator is pure (subject + cohort -> verdict), so these tests need no
database; the DB-backed price-history test lives at the bottom.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.enums import DealType, PropertyType, ValuationStatus  # noqa: E402
from app.models.property import Property  # noqa: E402
from app.services import geo, valuation  # noqa: E402
from app.services.valuation import Comparable, evaluate, label_for  # noqa: E402

# Tehran prices run tens of millions of Toman per square metre.
PPSQM = 60_000_000


def _subject(price_per_meter: float, *, area: float = 100.0, rooms: int = 2) -> Property:
    prop = Property(
        title="subject", property_type=PropertyType.APARTMENT, deal_type=DealType.SALE
    )
    prop.area = area
    prop.rooms = rooms
    prop.total_price = int(price_per_meter * area)
    return prop


def _cohort(n: int = 12, ppsqm: float = PPSQM, distance: float = 300.0) -> list[Comparable]:
    # Spread the values slightly so the MAD trimmer has something to work with.
    return [
        Comparable(
            property_id=str(i),
            price_per_meter=ppsqm + (i - n // 2) * 100_000,
            distance_m=distance,
            weight=1.0,
        )
        for i in range(n)
    ]


# -- pure estimator -----------------------------------------------------------


def test_fair_price_near_median():
    result = evaluate(_subject(PPSQM), _cohort())
    assert result.status is ValuationStatus.FAIR
    assert abs(result.deviation_pct) < 15


def test_bargain_20pct_below_median():
    result = evaluate(_subject(PPSQM * 0.80), _cohort())
    assert result.status is ValuationStatus.BARGAIN
    assert result.is_bargain
    assert result.deviation_pct <= -15


def test_overpriced_above_median():
    assert evaluate(_subject(PPSQM * 1.30), _cohort()).status is ValuationStatus.OVERPRICED


@pytest.mark.parametrize(
    "deviation,expected",
    [
        (-40.0, ValuationStatus.BARGAIN),
        (-15.0, ValuationStatus.BARGAIN),   # bargain threshold is inclusive
        (-14.9, ValuationStatus.FAIR),
        (5.0, ValuationStatus.FAIR),
        (10.0, ValuationStatus.FAIR),      # overpriced threshold is exclusive
        (10.1, ValuationStatus.OVERPRICED),
    ],
)
def test_label_thresholds(deviation, expected):
    assert label_for(deviation) is expected


def test_unknown_without_price():
    prop = _subject(PPSQM)
    prop.total_price = None
    result = evaluate(prop, _cohort())
    assert result.status is ValuationStatus.UNKNOWN
    assert result.explain["reason"] == "missing_price_or_area"


def test_unknown_with_empty_cohort():
    result = evaluate(_subject(PPSQM), [])
    assert result.status is ValuationStatus.UNKNOWN
    assert result.explain["reason"] == "empty_cohort"


def test_unknown_when_sample_below_minimum():
    result = evaluate(_subject(PPSQM), _cohort(n=4))
    assert result.status is ValuationStatus.UNKNOWN
    assert result.explain["reason"] == "insufficient_samples"


def test_impossible_prices_are_dropped_not_averaged_in():
    cohort = _cohort() + [
        Comparable("junk-1", 900_000_000, 100.0, 1.0),
        Comparable("junk-2", 950_000_000, 100.0, 1.0),
    ]
    result = evaluate(_subject(PPSQM), cohort)
    assert result.explain["dropped_outliers"] == 2
    assert result.status is ValuationStatus.FAIR


def test_median_is_robust_to_one_luxury_tower():
    """A mean would be dragged upward; the weighted median must barely move."""
    baseline = evaluate(_subject(PPSQM), _cohort())
    with_outlier = _cohort() + [Comparable("tower", PPSQM * 20, 100.0, 1.0)]
    result = evaluate(_subject(PPSQM), with_outlier)
    assert result.median_price_per_meter == pytest.approx(
        baseline.median_price_per_meter, rel=0.05
    )


def test_rent_compares_annualised_rent():
    prop = _subject(0)          # no asking price at all
    prop.deal_type = DealType.RENT
    prop.monthly_rent = int(PPSQM * 100 / 12)
    assert evaluate(prop, _cohort()).status is ValuationStatus.FAIR


def test_result_is_explainable():
    result = evaluate(_subject(PPSQM * 0.7), _cohort())
    for key in ("cohort_size", "n_valid", "observed_ppsqm", "median_ppsqm",
                "window_days", "min_samples", "thresholds"):
        assert key in result.explain


# -- weighting / cohort helpers ----------------------------------------------


def test_near_comparables_outweigh_distant_ones():
    assert valuation.radius_weight(100) > valuation.radius_weight(1500)
    assert valuation.radius_weight(1500) > valuation.radius_weight(4000)


def test_bedroom_bucket_collapses_4_plus():
    assert valuation.bedroom_bucket(None) == 0
    assert valuation.bedroom_bucket(0) == 0
    assert valuation.bedroom_bucket(3) == 3
    assert valuation.bedroom_bucket(9) == 4


# -- geo helpers --------------------------------------------------------------


def test_point_distance_is_zero_for_same_point():
    assert geo.point_distance_m(35.7, 51.4, 35.7, 51.4) == pytest.approx(0.0, abs=1e-6)


def test_point_distance_matches_known_separation():
    # ~1.1 km north-south along a meridian.
    assert 1000 < geo.point_distance_m(35.70, 51.40, 35.71, 51.40) < 1200


# -- price-history idempotency (DB-backed, in-memory SQLite) ------------------


async def test_record_price_appends_then_becomes_a_noop():
    """Re-submitting the same price must not add a second timeline row."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlmodel import select
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models import PropertyPriceHistory
    from app.models.enums import PriceChangeSource
    from app.services.submission import record_price
    from tests.conftest import create_sqlite_schema

    engine = create_async_engine("sqlite+aiosqlite://")
    await create_sqlite_schema(engine, "property", "property_price_history")
    try:
        async with AsyncSession(engine) as session:
            prop = Property(title="unit", total_price=100_000_000, area=100.0)
            session.add(prop)
            await session.commit()
            await session.refresh(prop)
            # commit() expires every attribute; capture the id now so the
            # post-commit query below does not trigger a lazy sync refresh.
            prop_id = prop.id

            first = await record_price(
                session, prop, new_price=110_000_000, source=PriceChangeSource.OWNER
            )
            assert first is not None
            assert first.price_difference == 10_000_000
            assert first.change_percentage == pytest.approx(10.0)
            assert prop.price_per_meter == 1_100_000

            unchanged = await record_price(
                session, prop, new_price=110_000_000, source=PriceChangeSource.OWNER
            )
            assert unchanged is None

            await session.commit()
            rows = (
                await session.exec(
                    select(PropertyPriceHistory).where(
                        PropertyPriceHistory.property_id == prop_id
                    )
                )
            ).all()
            assert len(rows) == 1
    finally:
        await engine.dispose()


async def test_record_price_handles_the_first_observed_price():
    """A listing ingested with no prior price must still open a timeline row."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.enums import PriceChangeSource
    from app.services.submission import record_price
    from tests.conftest import create_sqlite_schema

    engine = create_async_engine("sqlite+aiosqlite://")
    await create_sqlite_schema(engine, "property", "property_price_history")
    try:
        async with AsyncSession(engine) as session:
            prop = Property(title="new listing", area=90.0)
            session.add(prop)
            await session.commit()
            await session.refresh(prop)

            entry = await record_price(
                session, prop, new_price=5_400_000_000, source=PriceChangeSource.SCRAPER
            )
            assert entry is not None
            assert entry.previous_price is None
            assert entry.change_percentage == 0.0
            assert prop.total_price == 5_400_000_000
            assert prop.price_per_meter == 60_000_000
            await session.commit()
    finally:
        await engine.dispose()


# -- submission guards --------------------------------------------------------


def test_validate_pin_rejects_a_point_outside_iran():
    from app.services.submission import validate_pin

    validate_pin(35.7, 51.4)          # Tehran
    with pytest.raises(ValueError):
        validate_pin(48.85, 2.35)     # Paris


def test_specs_match_tolerates_three_percent_area_drift():
    from app.services.submission import specs_match

    existing = Property(title="known", property_type=PropertyType.APARTMENT, area=100.0)
    existing.rooms = 3
    assert specs_match(
        existing, area=102.0, rooms=3, property_type=PropertyType.APARTMENT
    )
    assert not specs_match(
        existing, area=110.0, rooms=3, property_type=PropertyType.APARTMENT
    )
    assert not specs_match(
        existing, area=100.0, rooms=2, property_type=PropertyType.APARTMENT
    )
    assert not specs_match(
        existing, area=100.0, rooms=3, property_type=PropertyType.VILLA
    )


def test_price_source_covers_every_channel():
    from app.models.enums import PriceChangeSource

    assert {s.value for s in PriceChangeSource} == {"SCRAPER", "MANUAL", "OWNER", "AVM"}