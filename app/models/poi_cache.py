"""``PoiCache`` -- nearby-points-of-interest results, cached per city block.

Overpass is a free public service with no SLA. Querying it once per listing
render would be both rude and a reliable way to get this node's IP throttled, so
results are stored against a ~100 m grid cell with a 7-day TTL: the answer for a
given block does not meaningfully change inside a week, and every listing on the
same street shares one row.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlmodel import SQLModel, Field

from app.models.base import point_column, timestamp_column, utcnow, uuid_column

#: Grid resolution in degrees. 0.001° is ~111 m, which is a city block.
POI_CELL_DEGREES = 0.001

#: How long a cached answer stays fresh.
POI_TTL_DAYS = 7


def cell_for(lat: float, lng: float) -> tuple[float, float]:
    """Quantise a coordinate onto the cache grid.

    Rounding rather than flooring so the cell centre is a round number, which
    keeps the stored geometry tidy and the unique index stable.
    """
    return (
        round(lat / POI_CELL_DEGREES) * POI_CELL_DEGREES,
        round(lng / POI_CELL_DEGREES) * POI_CELL_DEGREES,
    )


def is_fresh(fetched_at: datetime, *, ttl_days: int = POI_TTL_DAYS) -> bool:
    """Whether a cached row is still inside its TTL."""
    return fetched_at >= utcnow() - timedelta(days=ttl_days)


class PoiCache(SQLModel, table=True):
    """One grid cell's worth of nearby amenities."""

    __tablename__ = "poi_cache"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())

    cell_lat: float = Field(index=True)
    cell_lng: float = Field(index=True)
    #: Geometry mirror of the cell centre; the GiST index on it answers the
    #: "which cached cells are near me" sweep.
    point: Any = Field(default=None, sa_column=point_column(nullable=False))
    #: ``{"transport": [...], "shopping": [...], "education": [...], ...}``
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB().with_variant(JSON(), "sqlite"), nullable=False),
    )

    fetched_at: datetime = Field(
        default_factory=utcnow, sa_column=timestamp_column()
    )