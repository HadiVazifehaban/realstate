"""Board header totals: per-column depth, pipeline value and win rate.

The arithmetic lives in `crm_service._aggregate`, so it is asserted here without
a database; the grouped SQL is exercised by the integration test at the bottom,
which only runs when a migrated PostGIS node is reachable.

Rules that carry real risk for a broker reading the header:

* the archive is *not* a sixth column -- it is reported separately, or the
  header would advertise a column the board cannot render;
* the win rate ignores deals still being worked, because counting them would
  make a busy desk look like a failing one;
* the value of a column is the sum of its listings' asking prices, so a lead
  whose listing is unpriced contributes a count but no value.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete, text

from app.models import CrmLead, LeadInteraction, Property
from app.models.enums import LeadStage, PropertySource
from app.schemas.crm import BoardStatsResponse, StageStat
from app.services import crm as crm_service


def _row(stage: LeadStage, count: int, value: int) -> tuple[LeadStage, int, int]:
    return (stage, count, value)


def _as_response(stats: crm_service.BoardStats) -> BoardStatsResponse:
    """Mirror what the route builds, so the wire shape is asserted too."""
    return BoardStatsResponse(
        total=stats.total,
        columns=[
            StageStat(
                stage=column.stage,
                count=column.count,
                total_value=column.total_value,
            )
            for column in stats.columns
        ],
        lost=stats.lost,
        bargains=stats.bargains,
        open_value=stats.open_value,
        closed_value=stats.closed_value,
        conversion_pct=stats.conversion_pct,
    )


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def test_an_empty_board_is_all_zeroes() -> None:
    stats = crm_service._aggregate([], bargains=0)

    assert stats.total == 0
    assert stats.lost == 0
    assert stats.conversion_pct == 0.0
    assert stats.open_value == 0
    # Every live column is present even when empty, so the header renders five
    # stable slots instead of shifting as deals arrive.
    assert [column.stage for column in stats.columns] == list(LeadStage)[:5]
    assert all(column.count == 0 for column in stats.columns)


def test_the_archive_never_becomes_a_column() -> None:
    stats = crm_service._aggregate(
        [_row(LeadStage.NEW_FILE, 3, 900), _row(LeadStage.LOST_ARCHIVED, 7, 0)],
        bargains=1,
    )

    assert stats.total == 10
    assert stats.lost == 7
    assert LeadStage.LOST_ARCHIVED not in [column.stage for column in stats.columns]
    # The 7 archived deals are counted once, in `lost`, not inside a column.
    assert sum(column.count for column in stats.columns) == 3


def test_column_value_is_the_sum_of_asking_prices() -> None:
    stats = crm_service._aggregate(
        [
            _row(LeadStage.APPRAISAL, 2, 4_500_000_000),
            _row(LeadStage.CLOSED_DEAL, 1, 1_200_000_000),
        ],
        bargains=2,
    )

    appraisal = next(c for c in stats.columns if c.stage is LeadStage.APPRAISAL)
    assert appraisal.count == 2
    assert appraisal.total_value == 4_500_000_000
    assert stats.open_value == 4_500_000_000
    assert stats.closed_value == 1_200_000_000
    assert stats.bargains == 2


def test_win_rate_ignores_deals_still_in_play() -> None:
    stats = crm_service._aggregate(
        [
            _row(LeadStage.NEW_FILE, 40, 0),
            _row(LeadStage.CLOSED_DEAL, 3, 0),
            _row(LeadStage.LOST_ARCHIVED, 1, 0),
        ],
        bargains=0,
    )

    # 3 won, 1 lost: the 40 open files are not part of the denominator.
    assert stats.conversion_pct == 75.0


def test_a_column_without_a_price_contributes_count_but_no_value() -> None:
    stats = crm_service._aggregate([_row(LeadStage.CONTACTING, 2, 0)], bargains=0)

    contacting = next(c for c in stats.columns if c.stage is LeadStage.CONTACTING)
    assert contacting.count == 2
    assert contacting.total_value == 0


def test_the_payload_the_board_consumes_serialises_cleanly() -> None:
    stats = crm_service._aggregate(
        [_row(LeadStage.CONTRACT_READY, 1, 2_000_000_000)], bargains=0
    )

    body = _as_response(stats).model_dump(mode="json")

    assert body["total"] == 1
    assert body["columns"][3] == {
        "stage": "CONTRACT_READY",
        "count": 1,
        "total_value": 2_000_000_000,
    }


# --------------------------------------------------------------------------- #
# Integration -- the grouped query against a real node
# --------------------------------------------------------------------------- #
@pytest.fixture()
async def db_ready() -> None:
    from app.db.session import engine

    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT to_regclass('public.crm_lead') IS NOT NULL")
            )
            if not bool(result.scalar()):
                raise RuntimeError("schema missing")
    except Exception:  # noqa: BLE001
        pytest.skip("PostgreSQL/PostGIS not available")


async def test_grouped_query_counts_real_leads(db_ready: None) -> None:
    from app.db.session import AsyncSessionLocal

    prop = Property(
        title="آپارتمان آمار تخته",
        location="SRID=4326;POINT(51.4100 35.7100)",
        total_price=3_500_000_000,
        source=PropertySource.INTERNAL_USER,
    )
    session = AsyncSessionLocal()
    session.add(prop)
    await session.flush()

    lead = CrmLead(property_id=prop.id, stage=LeadStage.NEW_FILE, is_bargain=True)
    session.add(lead)
    await session.commit()

    try:
        stats = await crm_service.board_stats(session)

        column = next(c for c in stats.columns if c.stage is LeadStage.NEW_FILE)
        assert column.count >= 1
        assert column.total_value >= 3_500_000_000
        assert stats.bargains >= 1
        # The header's total is exactly the columns plus the archive -- never
        # more, or the board and its header would disagree on depth.
        assert stats.total == sum(c.count for c in stats.columns) + stats.lost
    finally:
        await session.execute(
            delete(LeadInteraction).where(LeadInteraction.lead_id == lead.id)
        )
        await session.execute(delete(CrmLead).where(CrmLead.id == lead.id))
        await session.execute(delete(Property).where(Property.id == prop.id))
        await session.commit()
        await session.close()


def test_the_stats_payload_carries_nothing_to_leak() -> None:
    """The header is an aggregate: no lead ids, no listing data, no owner PII."""
    stats = crm_service._aggregate([_row(LeadStage.NEW_FILE, 1, 1)], bargains=0)

    body = _as_response(stats).model_dump(mode="json")

    assert set(body) == {
        "total",
        "columns",
        "lost",
        "bargains",
        "open_value",
        "closed_value",
        "conversion_pct",
    }
    assert set(body["columns"][0]) == {"stage", "count", "total_value"}
