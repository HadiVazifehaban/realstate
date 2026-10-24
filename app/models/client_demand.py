"""``ClientDemand`` -- the applicant/request ledger (کاردکس متقاضیان)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger
from sqlmodel import SQLModel, Field, Column

from app.models.base import (
    pg_enum,
    polygon_column,
    timestamp_column,
    utcnow,
    uuid_column,
)
from app.models.enums import DealType, DemandStatus

_DealCol = Column(pg_enum(DealType, "demand_deal_type"), nullable=False)
_StatusCol = Column(pg_enum(DemandStatus, "demand_status"), nullable=False, index=True)


class ClientDemand(SQLModel, table=True):
    """A buyer/tenant request used by the deterministic matching engine."""

    __tablename__ = "client_demand"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    client_name: str = Field(default="", max_length=255)
    client_phone: str = Field(default="", max_length=32, index=True)
    client_phone_alt: str = Field(default="", max_length=32)
    notes: str = Field(default="", description="یادداشت رفتاری مشتری")

    deal_type: DealType = Field(default=DealType.SALE, sa_column=_DealCol)
    status: DemandStatus = Field(default=DemandStatus.NEW, sa_column=_StatusCol)
    priority: int = Field(default=0)

    # -- Technical filters ------------------------------------------------------
    min_area: float | None = Field(default=None)
    max_area: float | None = Field(default=None)
    min_rooms: int | None = Field(default=None)
    max_rooms: int | None = Field(default=None)
    max_building_age: int | None = Field(default=None, description="حداکثر سن بنا")
    requires_elevator: bool = Field(default=False)
    requires_parking: bool = Field(default=False)
    requires_storage: bool = Field(default=False)
    preferred_types: str = Field(default="", description="انواع ملک مورد علاقه، جدا با کاما")

    # -- Budget -----------------------------------------------------------------
    # BIGINT: Toman amounts exceed the 2^31-1 ceiling of INTEGER.
    min_total_price: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    max_total_price: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    min_deposit: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    max_deposit: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    max_monthly_rent: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )

    # -- Target geography -------------------------------------------------------
    target_area: Any = Field(default=None, sa_column=polygon_column(nullable=True))
    target_neighborhoods: str = Field(default="", description="محله‌های هدف، جدا با کاما")
    center_lat: float | None = Field(default=None)
    center_lng: float | None = Field(default=None)
    radius_meters: int | None = Field(default=None)

    created_by_id: uuid.UUID | None = Field(default=None, foreign_key="agency_user.id")
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
