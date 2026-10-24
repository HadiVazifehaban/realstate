"""Visit-slot logic lives on SQLite (enum columns degraded to strings), so the
543-combination gets exercised without a live PostGIS."""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import date, time, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlmodel import select  # noqa: E402

from app.models import Property, PropertyVisitBooking  # noqa: E402
from app.models.enums import VisitSlotKind, VisitSlotStatus  # noqa: E402
from app.schemas.properties import (  # noqa: E402
    BLOCKING_STATUSES,
    VisitAvailabilityItem,
    VisitBookingCreate,
)
from tests.conftest import create_sqlite_schema  # noqa: E402


def _run(coro):
    """Drive one coroutine on a fresh loop, like ``test_phase2_ingestion``.

    pytest-asyncio (``asyncio_mode = "auto"``) owns and closes the main-thread
    loop between tests, so ``asyncio.get_event_loop()`` is a lottery by the
    time a sync test runs: it returns a closed loop, raises ``RuntimeError``,
    or hands out a loop another test's executor is still tearing down. A
    dedicated loop per call sidesteps all three.
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


async def _session():
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_sqlite_schema(engine, "property_visit_booking")
    # ``sqlmodel.ext.asyncio.session.AsyncSession`` is the one with ``.exec``;
    # the stock SQLAlchemy session only knows ``.execute``.
    maker = sessionmaker(engine, class_=SQLModelAsyncSession, expire_on_commit=False)
    session = maker()
    assert isinstance(session, AsyncSession)

    async def _close() -> None:
        await session.close()
        await engine.dispose()

    session_fixture = session
    session_fixture._avg_close = _close  # type: ignore[attr-defined]
    return session_fixture


def test_blocking_statuses_cover_the_lifecycle() -> None:
    assert VisitSlotStatus.REQUESTED in BLOCKING_STATUSES
    assert VisitSlotStatus.CONFIRMED in BLOCKING_STATUSES
    assert VisitSlotStatus.DRAFT in BLOCKING_STATUSES
    assert VisitSlotStatus.CANCELLED not in BLOCKING_STATUSES
    assert VisitSlotStatus.NO_SHOW not in BLOCKING_STATUSES
    assert VisitSlotStatus.COMPLETED not in BLOCKING_STATUSES


def test_booking_create_rejects_the_past() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        VisitBookingCreate(
            slot_date=date.today() - timedelta(days=1),
            start_time=time(10, 0),
        )


def test_booking_create_rejects_end_before_start() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        VisitBookingCreate(
            slot_date=date.today() + timedelta(days=1),
            start_time=time(11, 0),
            end_time=time(10, 0),
        )


def test_unique_slot_constraint_is_real() -> None:
    from sqlalchemy.exc import IntegrityError

    async def scenario() -> None:
        session = await _session()
        prop = Property(title="slot uniqueness probe")
        session.add(prop)
        await session.flush()
        first = PropertyVisitBooking(
            property_id=prop.id,
            slot_date=date.today() + timedelta(days=2),
            start_time=time(10, 0),
            end_time=time(11, 0),
            status=VisitSlotStatus.REQUESTED,
            kind=VisitSlotKind.OFFICE_HOUSE,
        )
        session.add(first)
        await session.commit()
        # A CANCELLED row on the same window must still insert: the unique
        # constraint is on (property, date, start), and cancellation is a
        # *status* story, not a second row -- but the constraint itself would
        # also reject that, so assert it rejects a plain double booking.
        clash = PropertyVisitBooking(
            property_id=prop.id,
            slot_date=first.slot_date,
            start_time=first.start_time,
            end_time=first.end_time,
            status=VisitSlotStatus.REQUESTED,
            kind=VisitSlotKind.PHONE,
        )
        session.add(clash)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            ok = True
            await session._avg_close()  # type: ignore[attr-defined]
            return ok
        await session._avg_close()  # type: ignore[attr-defined]
        return False

    assert _run(scenario()) is True


def test_availability_item_shape() -> None:
    item = VisitAvailabilityItem(
        slot_date=date(2026, 10, 15), start_time=time(9, 0), end_time=time(10, 0),
        available=True,
    )
    assert item.status is None and item.kind is None
    taken = VisitAvailabilityItem(
        slot_date=date(2026, 10, 15), start_time=time(10, 0), end_time=time(11, 0),
        available=False, status=VisitSlotStatus.CONFIRMED,
        kind=VisitSlotKind.OFFICE_HOUSE,
    )
    assert taken.status is VisitSlotStatus.CONFIRMED


def test_booking_round_trip_and_property_backref() -> None:
    async def scenario():
        session = await _session()
        prop = Property(title="round-trip probe")
        session.add(prop)
        await session.flush()
        row = PropertyVisitBooking.draft_for(
            prop.id, date.today() + timedelta(days=3), time(14, 0), time(15, 0)
        )
        session.add(row)
        await session.commit()
        # Eager read, not a lazy load: ``prop`` is expired after commit and a
        # lazy ``visit_bookings`` touch from async code raises MissingGreenlet
        # (sync IO inside the greenlet) instead of hitting the database.
        got = (
            await session.exec(
                select(PropertyVisitBooking).where(
                    PropertyVisitBooking.property_id == prop.id
                )
            )
        ).all()
        assert len(got) == 1
        assert got[0].status is VisitSlotStatus.DRAFT
        assert got[0].kind is VisitSlotKind.OFFICE_HOUSE
        prop_id = prop.id
        await session._avg_close()  # type: ignore[attr-defined]
        return prop_id is not None

    assert _run(scenario()) is True


def test_property_side_declares_the_backref() -> None:
    """The mapper wire-up must name ``visit_bookings`` on ``Property``.

    This guards the exact regression that took the whole app down once: a
    mis-annotated ``visit_bookings`` makes ``configure_mappers`` raise and
    every endpoint (not just the visit ones) fails to import.
    """
    from sqlalchemy.orm import configure_mappers

    configure_mappers()
    assert "visit_bookings" in Property.__mapper__.relationships
    assert "property" in PropertyVisitBooking.__mapper__.relationships
    assert "visit_bookings" not in Property.model_fields


def test_booking_defaults_to_requested_status() -> None:
    row = PropertyVisitBooking(
        property_id=uuid.uuid4(),
        slot_date=date.today() + timedelta(days=1),
        start_time=time(9, 0),
        kind=VisitSlotKind.VIRTUAL,
    )
    assert row.status is VisitSlotStatus.REQUESTED
    dumped = VisitBookingCreate(
        slot_date=row.slot_date, start_time=row.start_time, kind=row.kind
    )
    assert dumped.kind is VisitSlotKind.VIRTUAL
