"""Phase 5 CRM pipeline service: leads, guarded stage transitions, timeline.

Rules are enforced here rather than in the router so every caller (API,
scheduler, a future WebSocket broadcaster) gets identical guarantees:

* A stage can only move along :data:`LEAD_TRANSITIONS`; anything else raises
  ``InvalidTransition``.
* Reopening a terminal stage is reserved for ADMIN.
* Every transition appends a ``STAGE_CHANGED`` interaction, so the board and the
  timeline can never disagree.
* Visit appointments are stored as ``VISIT_EVENT`` interactions carrying a
  ``scheduled_at`` timestamp. No ``visit_date`` exists on a property, and this
  module never introduces one.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models import CrmLead, LeadInteraction, Property
from app.models.enums import (
    KANBAN_COLUMNS,
    LEAD_TRANSITIONS,
    LEGACY_SOURCE_ALIASES,
    InteractionType,
    LeadPriority,
    LeadStage,
    PropertySource,
    UserRole,
    ValuationStatus,
)


class LeadError(Exception):
    """Base class for pipeline rule violations."""


class InvalidTransition(LeadError):
    """The requested stage move is not in ``LEAD_TRANSITIONS``."""


class TransitionNotPermitted(LeadError):
    """The actor's role may not perform this particular move."""


@dataclass(frozen=True)
class StageStat:
    """One column of the board header: how deep it is and what it is worth."""

    stage: LeadStage
    count: int
    #: Sum of the linked listings' asking prices. 0 means "none priced", which
    #: is indistinguishable from a free-of-charge listing -- the header shows a
    #: dash rather than guessing.
    total_value: int


@dataclass(frozen=True)
class BoardStats:
    """Desk totals, computed over every lead rather than the card page."""

    total: int
    #: The five live columns, in board order. The archive is reported separately
    #: so the header cannot accidentally render a sixth column.
    columns: list[StageStat]
    lost: int
    bargains: int
    #: Value still in play -- the four columns before CLOSED_DEAL -- vs. banked.
    open_value: int
    closed_value: int
    #: Won / (won + lost). Deals still being worked are excluded on purpose:
    #: counting them would make a busy desk look like a failing one.
    conversion_pct: float


@dataclass(frozen=True)
class LeadView:
    """Board projection of a lead — safe to serialise (carries no owner PII)."""

    id: uuid.UUID
    property_id: uuid.UUID
    stage: LeadStage
    priority: LeadPriority
    assigned_user_id: uuid.UUID | None
    is_bargain: bool
    deviation_pct: float | None
    neighborhood: str
    city: str
    title: str
    total_price: int | None
    area: float | None
    rooms: int | None
    updated_at: datetime
    #: Mirrors `Property.source` on the linked listing, so the board can show
    #: provenance (owner / agent / portal) without a second fetch per card.
    #: None when the lead predates the column.
    source: PropertySource | None = None


def priority_for(
    valuation: ValuationStatus, deviation_pct: float | None
) -> LeadPriority:
    """A bargain lead outranks ordinary inventory on the board."""
    if valuation is ValuationStatus.BARGAIN:
        return LeadPriority.URGENT_BARGAIN
    if valuation is ValuationStatus.OVERPRICED:
        return LeadPriority.LOW
    return LeadPriority.NORMAL


def assert_transition_allowed(
    current: LeadStage, target: LeadStage, *, role: UserRole
) -> None:
    """Raise unless ``current -> target`` is legal for ``role``."""
    if target not in LEAD_TRANSITIONS.get(current, frozenset()):
        raise InvalidTransition(
            f"انتقال غیرمجاز از {current.value} به {target.value}"
        )
    # Reopening a terminal stage is a governance action, not a desk action.
    if current in (LeadStage.CLOSED_DEAL, LeadStage.LOST_ARCHIVED):
        if role is not UserRole.ADMIN:
            raise TransitionNotPermitted(
                "بازگشایی پروندهٔ بسته تنها با نقش مدیر ارشد ممکن است."
            )


def _to_view(lead: CrmLead, prop: Property) -> LeadView:
    return LeadView(
        id=lead.id,
        property_id=lead.property_id,
        stage=lead.stage,
        priority=lead.priority,
        assigned_user_id=lead.assigned_user_id,
        is_bargain=lead.is_bargain,
        deviation_pct=lead.deviation_pct,
        neighborhood=lead.neighborhood or prop.neighborhood,
        city=lead.city or prop.city,
        title=prop.title,
        total_price=prop.total_price,
        area=prop.area,
        rooms=prop.rooms,
        updated_at=lead.updated_at,
        # Fold the legacy source names onto their canonical members. The node
        # still holds rows written before the rename (DIVAR_SCRAPER,
        # MANUAL_OFFICE), and the board's provenance labels are keyed by the
        # canonical enum -- serving the raw value makes the card badge render as
        # undefined and the lead look sourced from nowhere. Mirrors the same
        # mapping in properties.py so both surfaces agree.
        source=LEGACY_SOURCE_ALIASES.get(prop.source, prop.source),
    )


async def create_lead_for_property(
    session: AsyncSession,
    prop: Property,
    *,
    assigned_user_id: uuid.UUID | None = None,
) -> CrmLead | None:
    """Open a lead for a property, or return the existing one.

    Idempotent by property: re-running ingestion for the same listing must not
    stack duplicate cards on the desk.
    """
    existing = (
        await session.exec(
            select(CrmLead)
            .where(CrmLead.property_id == prop.id)
            .order_by(CrmLead.created_at)  # type: ignore[arg-type]
        )
    ).first()
    if existing is not None:
        return existing

    lead = CrmLead(
        property_id=prop.id,
        assigned_user_id=assigned_user_id,
        stage=LeadStage.NEW_FILE,
        priority=priority_for(prop.valuation_status, prop.valuation_deviation_pct),
        is_bargain=prop.valuation_status is ValuationStatus.BARGAIN,
        deviation_pct=prop.valuation_deviation_pct,
        neighborhood=prop.neighborhood,
        city=prop.city,
    )
    session.add(lead)
    await session.flush()
    return lead


async def move_lead(
    session: AsyncSession,
    lead: CrmLead,
    target: LeadStage,
    *,
    role: UserRole,
    actor_user_id: uuid.UUID | None = None,
    note: str = "",
) -> LeadInteraction:
    """Advance a lead one stage and append the matching timeline event."""
    assert_transition_allowed(lead.stage, target, role=role)

    previous = lead.stage
    lead.stage = target
    lead.updated_at = datetime.now().astimezone()

    event = LeadInteraction(
        lead_id=lead.id,
        actor_user_id=actor_user_id,
        interaction_type=InteractionType.STAGE_CHANGED,
        note=note or f"{previous.value} → {target.value}",
    )
    session.add(event)
    await session.flush()
    return event


async def log_interaction(
    session: AsyncSession,
    lead: CrmLead,
    *,
    interaction_type: InteractionType,
    actor_user_id: uuid.UUID | None = None,
    scheduled_at: datetime | None = None,
    note: str = "",
) -> LeadInteraction:
    """Append a timeline event.

    ``scheduled_at`` is only meaningful for ``VISIT_EVENT``; it is the one place
    an appointment time is allowed to live.
    """
    if interaction_type is InteractionType.VISIT_EVENT and scheduled_at is None:
        raise ValueError("رویداد بازدید به زمان‌بندی نیاز دارد.")

    event = LeadInteraction(
        lead_id=lead.id,
        actor_user_id=actor_user_id,
        interaction_type=interaction_type,
        scheduled_at=scheduled_at,
        note=note or None,
    )
    session.add(event)
    lead.updated_at = datetime.now().astimezone()
    await session.flush()
    return event


def _aggregate(
    rows: list[tuple[LeadStage, int, int]], bargains: int
) -> BoardStats:
    """Fold ``(stage, count, value)`` rows into the board header's totals.

    Split out from :func:`board_stats` so the arithmetic -- the win-rate
    denominator above all -- is testable without a database.
    """
    counted: dict[LeadStage, tuple[int, int]] = {
        stage: (0, 0) for stage in LeadStage
    }
    for stage, count, value in rows:
        counted[stage] = (int(count), int(value or 0))

    columns = [
        StageStat(stage=stage, count=counted[stage][0], total_value=counted[stage][1])
        for stage in KANBAN_COLUMNS
    ]
    lost = counted[LeadStage.LOST_ARCHIVED][0]
    closed_count, closed_value = counted[LeadStage.CLOSED_DEAL]
    decided = closed_count + lost

    return BoardStats(
        total=sum(column.count for column in columns) + lost,
        columns=columns,
        lost=lost,
        bargains=int(bargains),
        # "Still in play" stops before the closing column: money in a won deal
        # is banked, not pipeline, and a header that mixes the two overstates
        # what the desk still has to work for.
        open_value=sum(
            column.total_value
            for column in columns
            if column.stage is not LeadStage.CLOSED_DEAL
        ),
        closed_value=closed_value,
        conversion_pct=round(100.0 * closed_count / decided, 1) if decided else 0.0,
    )


async def board_stats(session: AsyncSession) -> BoardStats:
    """Desk totals for the board header.

    One grouped pass plus one bargain count, rather than a query per column: the
    header needs all five numbers before it can render, and the price lives on
    `property`, so the join has to happen either way.
    """
    rows = (
        await session.exec(
            select(
                CrmLead.stage,
                func.count(CrmLead.id),
                func.coalesce(func.sum(Property.total_price), 0),
            )
            .join(Property, Property.id == CrmLead.property_id)
            .group_by(CrmLead.stage)
        )
    ).all()
    bargains = (
        await session.exec(
            select(func.count(CrmLead.id)).where(CrmLead.is_bargain.is_(True))
        )
    ).one()
    return _aggregate(rows, bargains)


async def list_leads(
    session: AsyncSession,
    *,
    stages: list[LeadStage] | None = None,
    assigned_user_id: uuid.UUID | None = None,
    bargains_only: bool = False,
    limit: int = 100,
) -> list[LeadView]:
    """Board feed, most recently updated first."""
    query = select(CrmLead)
    if stages:
        query = query.where(CrmLead.stage.in_(stages))
    if assigned_user_id is not None:
        query = query.where(CrmLead.assigned_user_id == assigned_user_id)
    if bargains_only:
        query = query.where(CrmLead.is_bargain.is_(True))

    leads = (await session.exec(query.limit(limit))).all()
    if not leads:
        return []

    # One extra query for all properties, rather than N per row.
    by_id = {
        prop.id: prop
        for prop in (
            await session.exec(
                select(Property).where(
                    Property.id.in_([lead.property_id for lead in leads])
                )
            )
        ).all()
    }
    views = [
        _to_view(lead, by_id[lead.property_id])
        for lead in leads
        if lead.property_id in by_id
    ]
    views.sort(key=lambda view: view.updated_at, reverse=True)
    return views
