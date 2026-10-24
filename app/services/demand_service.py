"""CRUD for the ``ClientDemand`` request ledger (کاردکس متقاضیان).

Thin by design: validation lives in the schemas, scoring in the matching
engine. Status transitions are guarded so a CLOSED/LOST demand cannot be
silently revived by a PATCH.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.base import utcnow
from app.models.client_demand import ClientDemand
from app.models.enums import DealType, DemandStatus
from app.schemas.matching import ClientDemandCreate, ClientDemandUpdate

logger = get_logger("app.matching.demands")

_TERMINAL_DEMAND_STATUSES = (DemandStatus.CLOSED, DemandStatus.LOST)


def _parse_deal_type(raw: str | None) -> DealType | None:
    if raw is None:
        return None
    try:
        return DealType(str(raw).strip().upper())
    except ValueError:
        return None


def _parse_status(raw: str | None) -> DemandStatus | None:
    if raw is None:
        return None
    try:
        return DemandStatus(str(raw).strip().upper())
    except ValueError:
        return None


async def create_demand(
    session: AsyncSession, payload: ClientDemandCreate, *, created_by_id: uuid.UUID | None = None
) -> ClientDemand:
    """Persist a new demand; raises ``ValueError`` on a bad deal type."""
    deal = _parse_deal_type(payload.deal_type)
    if deal is None:
        raise ValueError(f"unknown deal_type {payload.deal_type!r}")
    demand = ClientDemand(
        client_name=payload.client_name or "",
        client_phone=payload.client_phone or "",
        client_phone_alt=payload.client_phone_alt or "",
        notes=payload.notes or "",
        deal_type=deal,
        status=DemandStatus.NEW,
        priority=payload.priority or 0,
        min_area=payload.min_area,
        max_area=payload.max_area,
        min_rooms=payload.min_rooms,
        max_rooms=payload.max_rooms,
        max_building_age=payload.max_building_age,
        requires_elevator=bool(payload.requires_elevator),
        requires_parking=bool(payload.requires_parking),
        requires_storage=bool(payload.requires_storage),
        preferred_types=payload.preferred_types or "",
        min_total_price=payload.min_total_price,
        max_total_price=payload.max_total_price,
        min_deposit=payload.min_deposit,
        max_deposit=payload.max_deposit,
        max_monthly_rent=payload.max_monthly_rent,
        target_neighborhoods=payload.target_neighborhoods or "",
        center_lat=payload.center_lat,
        center_lng=payload.center_lng,
        radius_meters=payload.radius_meters,
        created_by_id=created_by_id,
    )
    session.add(demand)
    await session.commit()
    await session.refresh(demand)
    logger.info("demand created %s", demand.id)
    return demand


async def get_demand(session: AsyncSession, demand_id: uuid.UUID) -> ClientDemand | None:
    return await session.get(ClientDemand, demand_id)


async def list_demands(
    session: AsyncSession,
    *,
    status: DemandStatus | None = None,
    deal_type: DealType | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ClientDemand], int]:
    stmt = select(ClientDemand)
    count_stmt = select(func.count()).select_from(ClientDemand)
    if status is not None:
        stmt = stmt.where(ClientDemand.status == status)
        count_stmt = count_stmt.where(ClientDemand.status == status)
    if deal_type is not None:
        stmt = stmt.where(ClientDemand.deal_type == deal_type)
        count_stmt = count_stmt.where(ClientDemand.deal_type == deal_type)
    total = int((await session.execute(count_stmt)).scalar() or 0)
    result = await session.execute(
        stmt.order_by(ClientDemand.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def update_demand(
    session: AsyncSession, demand: ClientDemand, payload: ClientDemandUpdate
) -> ClientDemand:
    """Apply a partial update; raises ``ValueError`` on bad enum/status moves."""
    data = payload.model_dump(exclude_unset=True)
    if "deal_type" in data and data["deal_type"] is not None:
        deal = _parse_deal_type(data.pop("deal_type"))
        if deal is None:
            raise ValueError(f"unknown deal_type {payload.deal_type!r}")
        demand.deal_type = deal
    if "status" in data and data["status"] is not None:
        target = _parse_status(data.pop("status"))
        if target is None:
            raise ValueError(f"unknown status {payload.status!r}")
        if demand.status in _TERMINAL_DEMAND_STATUSES and target not in _TERMINAL_DEMAND_STATUSES:
            raise ValueError(f"cannot reopen {demand.status.value} demand")
        demand.status = target
    for key, value in data.items():
        if value is not None and hasattr(demand, key):
            setattr(demand, key, value)
    demand.updated_at = utcnow()
    await session.commit()
    await session.refresh(demand)
    return demand


async def delete_demand(session: AsyncSession, demand: ClientDemand) -> None:
    await session.delete(demand)
    await session.commit()


__all__ = ["create_demand", "get_demand", "list_demands", "update_demand", "delete_demand"]
