"""DB-backed regression tests for the matching pipeline's persistence rules.

``test_matching_engine.py`` covers the pure scoring functions. These cover the
parts that only misbehave against a real database: idempotency, and the guard
that stops a re-run from resurrecting work an agent already triaged.
"""

from __future__ import annotations

import uuid
import os

import pytest
from sqlalchemy import select, text

from app.core.config import Settings
from app.models import ClientDemand, Property, PropertyMatch
from app.models.enums import (
    DealType,
    DemandStatus,
    MatchStatus,
    PropertySource,
    PropertyStatus,
    PropertyType,
)
from app.services import matching_service
from app.services.ingestion.sanitizer import to_ewkt_point

# A point inside the demand's target polygon below.
_LAT, _LNG = 35.7812, 51.4201

_TARGET_AREA = (
    "SRID=4326;POLYGON((51.30 35.60, 51.50 35.60, "
    "51.50 35.80, 51.30 35.80, 51.30 35.60))"
)


@pytest.fixture()
def db_session_factory(phase15_session_factory):
    """Use the explicitly preflight-approved isolated PostgreSQL fixture."""
    if os.getenv("SHEKARCHI_TEST_INTEGRATION") != "1":
        pytest.skip("matching persistence requires explicit Phase 1.6 isolated Integration opt-in")
    return phase15_session_factory


def _settings(**overrides) -> Settings:
    """Matching on, permissive threshold, so fixtures are the only variable."""
    return Settings(matching_enabled=True, matching_min_score=1.0, **overrides)


async def _seed(session_factory) -> tuple[uuid.UUID, uuid.UUID]:
    """Create one demand and one listing that comfortably match."""
    async with session_factory() as session:
        demand = ClientDemand(
            client_name="مشتری رگرسیون",
            deal_type=DealType.SALE,
            status=DemandStatus.QUALIFIED,
            min_rooms=2,
            max_rooms=3,
            min_area=100.0,
            max_area=140.0,
            min_total_price=1_000_000,
            max_total_price=90_000_000_000,
            target_area=_TARGET_AREA,
        )
        prop = Property(
            title="آپارتمان رگرسیون",
            property_type=PropertyType.APARTMENT,
            deal_type=DealType.SALE,
            status=PropertyStatus.ACTIVE,
            source=PropertySource.MANUAL_OFFICE,
            area=120.0,
            rooms=2,
            total_price=5_400_000_000,
            city="تهران",
            neighborhood="جردن",
            latitude=_LAT,
            longitude=_LNG,
            location=to_ewkt_point(_LAT, _LNG),
        )
        session.add(demand)
        session.add(prop)
        await session.commit()
        await session.refresh(demand)
        await session.refresh(prop)
        return prop.id, demand.id


async def _cleanup(session_factory, *match_ids: uuid.UUID, property_id: uuid.UUID, demand_id: uuid.UUID) -> None:
    async with session_factory() as session:
        for mid in match_ids:
            row = await session.get(PropertyMatch, mid)
            if row is not None:
                await session.delete(row)
        # Also sweep any match the demand picked up from unrelated listings so
        # the demand row below never leaves orphaned FK references behind.
        orphaned = (
            (
                await session.execute(
                    select(PropertyMatch).where(PropertyMatch.demand_id == demand_id)
                )
            )
            .scalars()
            .all()
        )
        for row in orphaned:
            await session.delete(row)
        for model, rid in ((Property, property_id), (ClientDemand, demand_id)):
            row = await session.get(model, rid)
            if row is not None:
                await session.delete(row)
        await session.commit()


async def test_retrigger_creates_then_updates_in_place(db_session_factory) -> None:
    """First run creates, second updates -- never a duplicate row."""
    session_factory = db_session_factory
    pid, did = await _seed(session_factory)
    try:
        async with session_factory() as session:
            demand = await session.get(ClientDemand, did)
            first = await matching_service.retrigger_demand(
                session, demand, settings=_settings()
            )
        # The counters are global across every plausible listing for this
        # demand, so the seeded pair is what we can assert on: the first run
        # must have created it (never updated a row it did not have yet).
        assert first["matches_created"] >= 1
        assert first["matches_updated"] == 0

        async with session_factory() as session:
            demand = await session.get(ClientDemand, did)
            second = await matching_service.retrigger_demand(
                session, demand, settings=_settings()
            )
        # The unique (property_id, demand_id) constraint makes a second row
        # impossible; the re-run must report it as an update. Nothing may be
        # *created* on a re-run -- that is what proves no duplicate rows.
        assert second["matches_created"] == 0
        assert second["matches_updated"] >= 1

        async with session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(PropertyMatch).where(
                            PropertyMatch.property_id == pid,
                            PropertyMatch.demand_id == did,
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert len(rows) == 1
    finally:
        async with session_factory() as session:
            existing = (
                (
                    await session.execute(
                        select(PropertyMatch).where(
                            PropertyMatch.property_id == pid, PropertyMatch.demand_id == did
                        )
                    )
                )
                .scalars()
                .all()
            )
        await _cleanup(session_factory, *[r.id for r in existing], property_id=pid, demand_id=did)


async def test_retrigger_does_not_resurrect_triaged_matches(db_session_factory) -> None:
    """CONTACTED/DISMISSED rows survive a re-run untouched and uncounted."""
    session_factory = db_session_factory
    pid, did = await _seed(session_factory)
    match_ids: list[uuid.UUID] = []
    try:
        async with session_factory() as session:
            demand = await session.get(ClientDemand, did)
            await matching_service.retrigger_demand(session, demand, settings=_settings())
        async with session_factory() as session:
            match = (
                (
                    await session.execute(
                        select(PropertyMatch).where(
                            PropertyMatch.property_id == pid,
                            PropertyMatch.demand_id == did,
                        )
                    )
                )
                .scalars()
                .one()
            )
            match_ids.append(match.id)
            # Freeze the triaged row's score so any later overwrite is visible.
            match.status = MatchStatus.CONTACTED
            match.score = 12.5
            match.specs_score = 1.5
            await session.commit()

        async with session_factory() as session:
            demand = await session.get(ClientDemand, did)
            result = await matching_service.retrigger_demand(
                session, demand, settings=_settings()
            )
        # The triaged pair must contribute nothing: no new row for it, and no
        # update either (see the frozen score assertions below). Unrelated
        # listings in the database may still be scored, so only the global
        # "created" counter -- which must stay zero -- is asserted here.
        assert result["matches_created"] == 0

        async with session_factory() as session:
            match = await session.get(PropertyMatch, match_ids[0])
            assert match.status is MatchStatus.CONTACTED
            assert match.score == 12.5
            assert match.specs_score == 1.5
    finally:
        await _cleanup(session_factory, *match_ids, property_id=pid, demand_id=did)


async def test_match_property_ignores_non_matchable_listing(db_session_factory) -> None:
    """An archived listing must not generate fresh suggestions."""
    session_factory = db_session_factory
    pid, did = await _seed(session_factory)
    match_ids: list[uuid.UUID] = []
    try:
        async with session_factory() as session:
            prop = await session.get(Property, pid)
            prop.status = PropertyStatus.ARCHIVED
            await session.commit()

        async with session_factory() as session:
            prop = await session.get(Property, pid)
            rows = await matching_service.match_property(
                session, prop, settings=_settings()
            )
        assert rows == []
    finally:
        async with session_factory() as session:
            existing = (
                (
                    await session.execute(
                        select(PropertyMatch).where(
                            PropertyMatch.property_id == pid,
                            PropertyMatch.demand_id == did,
                        )
                    )
                )
                .scalars()
                .all()
            )
            match_ids.extend(r.id for r in existing)
        await _cleanup(session_factory, *match_ids, property_id=pid, demand_id=did)
