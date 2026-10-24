"""``PropertyMatch`` -- the scored link between a property and a client demand.

Every ingested listing is scored against the active demands; rows below the
configured threshold are never written, so the table stays a work queue rather
than a dump. ``(property_id, demand_id)`` is unique so a re-scrape of the same
listing updates the score instead of creating duplicates.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Column, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field

from app.models.base import (
    pg_enum,
    timestamp_column,
    utcnow,
    uuid_column,
)
from app.models.enums import MatchStatus

_StatusCol = Column(
    pg_enum(MatchStatus, "match_status"), nullable=False, index=True
)
_BreakdownCol = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict)


class PropertyMatch(SQLModel, table=True):
    """One scored suggestion linking a listing to a client demand."""

    __tablename__ = "property_match"
    __table_args__ = (
        # One suggestion per (listing, demand): re-scoring updates in place.
        UniqueConstraint("property_id", "demand_id", name="uq_property_match_pair"),
        # The agent's main view: best-scoring suggestions for a demand first.
        Index("ix_property_match_demand_score", "demand_id", "score"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    property_id: uuid.UUID = Field(
        foreign_key="property.id", ondelete="CASCADE", nullable=False, index=True
    )
    demand_id: uuid.UUID = Field(
        foreign_key="client_demand.id", ondelete="CASCADE", nullable=False, index=True
    )

    # Deterministic 0..100 score plus the per-component breakdown and the
    # human-readable reasons shown to the agent.
    score: float = Field(default=0.0)
    geo_score: float = Field(default=0.0)
    price_score: float = Field(default=0.0)
    specs_score: float = Field(default=0.0)
    breakdown: dict[str, Any] = Field(default_factory=dict, sa_column=_BreakdownCol)

    status: MatchStatus = Field(default=MatchStatus.NEW, sa_column=_StatusCol)
    distance_meters: float | None = Field(
        default=None, description="فاصله تا مرکز/محدوده تقاضا"
    )

    created_at: datetime = Field(
        default_factory=utcnow, sa_column=timestamp_column(index=True)
    )
    updated_at: datetime = Field(
        default_factory=utcnow, sa_column=timestamp_column()
    )