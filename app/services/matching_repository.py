"""DB-backed matching: score a listing against active client demands.

Separates concerns:

* **candidate selection** — a cheap SQL pre-filter (deal type, status, hard
  budget bounds) so only plausible demands reach the scorer.
* **scoring** — the pure :mod:`app.services.matching_engine` helpers.
* **persistence** — upsert into ``property_match``; re-scoring a listing
  updates the existing row instead of duplicating the suggestion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.base import utcnow
from app.models.client_demand import ClientDemand
from app.models.enums import MATCHABLE_STATUSES, DemandStatus, DealType
from app.models.property import Property
from app.services.matching_engine import compute_match_score

logger = get_logger("app.matching.repository")

# Demands that are still worth matching against.
_ACTIVE_DEMAND_STATUSES = (
    DemandStatus.NEW,
    DemandStatus.QUALIFIED,
    DemandStatus.VISITING,
    DemandStatus.MATCHED,
)

# Listings worth offering to a demand; shared with the matching service via
# `MATCHABLE_STATUSES` so the two can never drift apart.
_MATCHABLE_PROPERTY_STATUSES = tuple(MATCHABLE_STATUSES)


@dataclass(frozen=True)
class ScoredMatch:
    """A scored (property, demand) pair, before persistence."""

    demand_id: str
    score: float
    geo_score: float
    price_score: float
    specs_score: float
    breakdown: dict[str, Any]
    distance_meters: float | None = None


def _parse_preferred_types(raw: str) -> set[str]:
    """``"apartment,villa"`` -> ``{"apartment", "villa"}``."""
    return {part.strip().upper() for part in (raw or "").split(",") if part.strip()}


async def spatial_context(
    session: AsyncSession, prop: Property, demand: ClientDemand
) -> tuple[bool | None, float | None]:
    """Resolve ``(inside_target_area, distance_meters)`` via PostGIS.

    * Polygon demand (``target_area`` set): ``ST_Contains`` check.
    * Radial demand (``center_lat/lng`` + ``radius_meters``): ``ST_Distance``
      in meters (geography cast) against the listing point.
    * Neither: ``(None, None)`` — the engine falls back to the neutral
      geo sub-score.

    Listings without coordinates also return ``(None, None)``.  Any DB error
    (e.g. geometry UDFs missing on SQLite) degrades to ``(None, None)``
    instead of failing the match — spatial scoring must never break a
    suggestion.
    """
    if prop.location is None:
        return None, None
    try:
        if demand.target_area is not None:
            stmt = select(func.ST_Contains(demand.target_area, prop.location))
            inside = bool((await session.execute(stmt)).scalar())
            return inside, None
        if (
            demand.center_lat is not None
            and demand.center_lng is not None
            and demand.radius_meters
        ):
            stmt = select(
                func.ST_Distance(
                    prop.location.cast(Geography),
                    func.ST_SetSRID(
                        func.ST_MakePoint(demand.center_lng, demand.center_lat), 4326
                    ).cast(Geography),
                )
            )
            distance = await session.execute(stmt)
            return None, float(distance.scalar() or 0.0)
    except Exception as exc:  # noqa: BLE001 - spatial is best-effort
        logger.debug("spatial context unavailable: %s", exc)
    return None, None


def candidate_demands_stmt(
    prop: Property, *, skip_ids: set[Any] | None = None
):
    """SQLAlchemy statement for demands that could plausibly match ``prop``.

    Hard filters only (cheap, index-friendly). Soft preferences (area band,
    elevator, ...) stay in the scorer so they influence the *score* instead of
    hiding the listing from the agent.
    """
    stmt = select(ClientDemand).where(
        ClientDemand.status.in_(_ACTIVE_DEMAND_STATUSES),
        ClientDemand.deal_type == prop.deal_type,
    )

    price = prop.total_price
    if price is not None:
        # Keep demands that do not exclude this price outright.
        stmt = stmt.where(
            or_(
                ClientDemand.min_total_price.is_(None),
                ClientDemand.min_total_price <= price,
            ),
            or_(
                ClientDemand.max_total_price.is_(None),
                ClientDemand.max_total_price >= price,
            ),
        )

    if skip_ids:
        stmt = stmt.where(ClientDemand.id.notin_(skip_ids))
    return stmt


async def find_candidate_demands(
    session: AsyncSession,
    prop: Property,
    *,
    limit: int = 500,
    exclude_ids: set[Any] | None = None,
) -> list[ClientDemand]:
    """Fetch demands worth scoring for this listing."""
    result = await session.execute(candidate_demands_stmt(prop, skip_ids=exclude_ids))
    return list(result.scalars().all()[:limit])


def score_against_demand(
    prop: Property,
    demand: ClientDemand,
    *,
    inside_target_area: bool | None = None,
    distance_meters: float | None = None,
) -> ScoredMatch:
    """Score one (listing, demand) pair using the deterministic engine."""
    building_age = None
    if prop.year_built:
        building_age = max(0, utcnow().year - int(prop.year_built))

    # Price semantics differ per deal type: a rent listing is compared against
    # the deposit, a sale listing against the total price.
    if prop.deal_type == DealType.RENT:
        price = prop.deposit_amount or prop.monthly_rent
        min_price = demand.min_deposit
        max_price = demand.max_deposit or demand.max_total_price
    else:
        price = prop.total_price
        min_price = demand.min_total_price
        max_price = demand.max_total_price

    breakdown = compute_match_score(
        # Spatial distance is supplied by the caller's PostGIS layer when
        # available; None keeps the neutral sub-score.
        inside_target_area=inside_target_area,
        distance_meters=distance_meters,
        radius_meters=demand.radius_meters,
        price=price,
        min_price=min_price,
        max_price=max_price,
        area=prop.area,
        min_area=demand.min_area,
        max_area=demand.max_area,
        rooms=prop.rooms,
        min_rooms=demand.min_rooms,
        max_rooms=demand.max_rooms,
        building_age=building_age,
        max_building_age=demand.max_building_age,
        floor=prop.floor,
        has_elevator=bool(prop.has_elevator),
        requires_elevator=demand.requires_elevator,
        has_parking=bool(prop.has_parking),
        requires_parking=demand.requires_parking,
    )
    return ScoredMatch(
        demand_id=str(demand.id),
        score=breakdown.total_score,
        geo_score=breakdown.geo_score,
        price_score=breakdown.price_score,
        specs_score=breakdown.specs_score,
        breakdown=breakdown.as_dict(),
    )


def candidate_properties_stmt(
    demand: ClientDemand, *, skip_ids: set[Any] | None = None
):
    """SQLAlchemy statement for listings that could plausibly satisfy ``demand``.

    The inverse of :func:`candidate_demands_stmt`: used by the manual
    "re-run matching" action, where we walk listings for one demand instead of
    demands for one listing. Same rule -- hard filters only; soft preferences
    stay in the scorer.
    """
    stmt = select(Property).where(
        Property.status.in_(_MATCHABLE_PROPERTY_STATUSES),
        Property.deal_type == demand.deal_type,
    )

    price_min, price_max = (
        (demand.min_deposit, demand.max_deposit or demand.max_total_price)
        if demand.deal_type == DealType.RENT
        else (demand.min_total_price, demand.max_total_price)
    )
    reference = price_min if price_min is not None else price_max
    if reference is not None:
        stmt = stmt.where(Property.total_price.is_not(None))
    if price_min is not None:
        stmt = stmt.where(Property.total_price >= price_min)
    if price_max is not None:
        stmt = stmt.where(Property.total_price <= price_max)

    if skip_ids:
        stmt = stmt.where(Property.id.notin_(skip_ids))
    return stmt


async def find_candidate_properties(
    session: AsyncSession,
    demand: ClientDemand,
    *,
    limit: int = 500,
    exclude_ids: set[Any] | None = None,
) -> list[Property]:
    """Fetch listings worth scoring for this demand."""
    result = await session.execute(candidate_properties_stmt(demand, skip_ids=exclude_ids))
    return list(result.scalars().all()[:limit])


def matches_threshold(
    scored: ScoredMatch, settings: Settings | None = None
) -> bool:
    """Only persist suggestions worth showing to an agent."""
    s = settings or get_settings()
    return scored.score >= s.matching_min_score


__all__ = [
    "ScoredMatch",
    "candidate_demands_stmt",
    "candidate_properties_stmt",
    "find_candidate_demands",
    "find_candidate_properties",
    "score_against_demand",
    "matches_threshold",
    "spatial_context",
]