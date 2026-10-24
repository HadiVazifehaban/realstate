"""Phase 3 matching pipeline: turn ingested listings into agent suggestions.

Registered as a subscriber to ``NewPropertyIngested`` so ingestion never waits
on matching (see :mod:`app.services.ingestion.pipeline`). Failure isolation is
provided by the event bus: a broken match never fails the scrape.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.enums import MATCHABLE_STATUSES, MatchStatus
from app.models.property import Property
from app.models.property_match import PropertyMatch
from app.services import matching_repository as repo
from app.services.events import NEW_PROPERTY_INGESTED, event_bus

logger = get_logger("app.matching.pipeline")

# Statuses a listing must have to be worth suggesting come from
# `MATCHABLE_STATUSES` so this service and the repository can never disagree.


async def match_property(
    session: AsyncSession,
    prop: Property,
    *,
    settings: Settings | None = None,
) -> list[PropertyMatch]:
    """Score ``prop`` against candidate demands and persist the good matches.

    Idempotent: an existing ``(property, demand)`` row is updated in place, so
    re-scraping a listing refreshes the score instead of duplicating rows.
    """
    s = settings or get_settings()
    if not s.matching_enabled:
        return []
    if prop.status not in MATCHABLE_STATUSES:
        logger.debug("property %s status %s not matchable", prop.id, prop.status)
        return []

    demands = await repo.find_candidate_demands(
        session,
        prop,
        limit=max(s.matching_max_demands_per_property, 1),
    )
    if not demands:
        return []

    scored = []
    for d in demands:
        inside, distance = await repo.spatial_context(session, prop, d)
        scored.append(repo.score_against_demand(prop, d, inside_target_area=inside, distance_meters=distance))
    winners = [sc for sc in scored if repo.matches_threshold(sc, s)]
    if not winners:
        return []

    demand_ids = {sc.demand_id for sc in winners}
    existing_result = await session.execute(
        select(PropertyMatch).where(
            PropertyMatch.property_id == prop.id,
            PropertyMatch.demand_id.in_(demand_ids),
        )
    )
    existing = {str(m.demand_id): m for m in existing_result.scalars().all()}

    rows: list[PropertyMatch] = []
    now = _utcnow()
    for sc in winners:
        row = existing.get(sc.demand_id)
        if row is None:
            row = PropertyMatch(
                property_id=prop.id,
                demand_id=uuid.UUID(sc.demand_id),
                status=MatchStatus.NEW,
            )
            session.add(row)
        row.score = sc.score
        row.geo_score = sc.geo_score
        row.price_score = sc.price_score
        row.specs_score = sc.specs_score
        row.breakdown = sc.breakdown
        row.distance_meters = sc.distance_meters
        row.updated_at = now
        rows.append(row)

    await session.commit()
    logger.info(
        "matched property %s to %d demand(s) (of %d scored)",
        prop.id,
        len(rows),
        len(scored),
        extra={"event": "property_matched", "property_id": str(prop.id)},
    )
    return rows


def _utcnow():
    from app.models.base import utcnow

    return utcnow()


async def list_matches(
    session: AsyncSession,
    *,
    demand_id: uuid.UUID | None = None,
    property_id: uuid.UUID | None = None,
    status: MatchStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PropertyMatch], int]:
    """The agent's suggestion queue, best score first.

    ``(demand_id, score)`` is indexed, so a demand's ranked worklist is cheap;
    a bare listing-wide view still resolves through that same index prefix.
    """
    stmt = select(PropertyMatch)
    count_stmt = select(func.count()).select_from(PropertyMatch)
    if demand_id is not None:
        stmt = stmt.where(PropertyMatch.demand_id == demand_id)
        count_stmt = count_stmt.where(PropertyMatch.demand_id == demand_id)
    if property_id is not None:
        stmt = stmt.where(PropertyMatch.property_id == property_id)
        count_stmt = count_stmt.where(PropertyMatch.property_id == property_id)
    if status is not None:
        stmt = stmt.where(PropertyMatch.status == status)
        count_stmt = count_stmt.where(PropertyMatch.status == status)

    total = int((await session.execute(count_stmt)).scalar() or 0)
    result = await session.execute(
        stmt.order_by(PropertyMatch.score.desc(), PropertyMatch.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def update_match_status(
    session: AsyncSession, match: PropertyMatch, status: MatchStatus
) -> PropertyMatch:
    """Move a suggestion through the agent's work queue."""
    match.status = status
    match.updated_at = _utcnow()
    session.add(match)
    await session.commit()
    await session.refresh(match)
    logger.info("match %s -> %s", match.id, status.value)
    return match


async def retrigger_demand(
    session: AsyncSession,
    demand,
    *,
    settings: Settings | None = None,
    limit: int = 500,
) -> dict[str, int]:
    """Re-score every plausible listing for one demand.

    Used by the desk's "re-run matching" action after the demand is widened
    (budget, radius, ...). Mirrors :func:`match_property` but walks listings
    instead of demands, so the response can report created vs updated.
    """
    s = settings or get_settings()
    if not s.matching_enabled:
        return {"matches_created": 0, "matches_updated": 0}

    candidates = await repo.find_candidate_properties(session, demand, limit=limit)
    created = updated = 0
    for prop in candidates:
        inside, distance = await repo.spatial_context(session, prop, demand)
        scored = repo.score_against_demand(
            prop, demand, inside_target_area=inside, distance_meters=distance
        )
        if not repo.matches_threshold(scored, s):
            continue

        existing = (
            await session.execute(
                select(PropertyMatch).where(
                    PropertyMatch.property_id == prop.id,
                    PropertyMatch.demand_id == demand.id,
                )
            )
        ).scalar_one_or_none()

        if existing is None:
            existing = PropertyMatch(property_id=prop.id, demand_id=demand.id)
            session.add(existing)
            created += 1
        # A re-score must not resurrect work the agent already triaged.
        elif existing.status in (MatchStatus.DISMISSED, MatchStatus.CONTACTED):
            continue
        else:
            updated += 1

        existing.score = scored.score
        existing.geo_score = scored.geo_score
        existing.price_score = scored.price_score
        existing.specs_score = scored.specs_score
        existing.breakdown = scored.breakdown
        existing.distance_meters = distance
        existing.updated_at = _utcnow()

    await session.commit()
    logger.info(
        "retriggered demand %s: %d created, %d updated",
        demand.id,
        created,
        updated,
    )
    return {"matches_created": created, "matches_updated": updated}


async def handle_new_property(
    session: AsyncSession | None = None,
    property_id: uuid.UUID | None = None,
    **_: Any,
) -> list[PropertyMatch]:
    """Event-bus handler for ``NewPropertyIngested``.

    Matches the **publisher's** session when provided so we see the freshly
    committed row; otherwise opens its own short-lived session.
    """
    if property_id is None:
        return []
    if session is not None:
        return await _handle_with_session(session, property_id)
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as own_session:
        return await _handle_with_session(own_session, property_id)


async def _handle_with_session(
    session: AsyncSession, property_id: uuid.UUID
) -> list[PropertyMatch]:
    prop = await session.get(Property, property_id)
    if prop is None:
        logger.warning("match requested for missing property %s", property_id)
        return []
    return await match_property(session, prop)


def register_matching_subscriber() -> bool:
    """Subscribe the matcher to ``NewPropertyIngested`` (idempotent)."""
    existing = event_bus.handlers_for(NEW_PROPERTY_INGESTED)
    if any(getattr(h, "__name__", "") == "handle_new_property" for h in existing):
        return False
    event_bus.subscribe(NEW_PROPERTY_INGESTED, handle_new_property)
    logger.info("matching subscriber registered")
    return True


def unregister_matching_subscriber() -> None:
    event_bus.unsubscribe(NEW_PROPERTY_INGESTED, handle_new_property)


__all__ = [
    "match_property",
    "list_matches",
    "update_match_status",
    "retrigger_demand",
    "handle_new_property",
    "register_matching_subscriber",
    "unregister_matching_subscriber",
]