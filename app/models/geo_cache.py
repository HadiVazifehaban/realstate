"""``GeoCache`` -- reverse-geocoding results cached per ~50 m grid cell.

Kept with the other tables (rather than in the service layer) so Alembic's
autogenerate and ``SQLModel.metadata`` agree with the ``geo_cache`` table
created by migration ``a4c1e2b3d4f5``.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

from sqlmodel import SQLModel, Field

from app.models.base import timestamp_column, utcnow, uuid_column

# ~50 m of latitude; enough to collapse the pins of one building.
GRID_DEGREES = 0.00045
CACHE_TTL_DAYS = 30


class GeoCache(SQLModel, table=True):
    """One reverse-geocoded grid cell (~50 m)."""

    __tablename__ = "geo_cache"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())

    grid_key: str = Field(unique=True, index=True, max_length=64)
    latitude: float = Field(description="مرکز سلول شبکه")
    longitude: float = Field(description="مرکز سلول شبکه")

    province: str = Field(default="", max_length=64)
    city: str = Field(default="", max_length=64)
    district: str = Field(default="", max_length=128)
    neighborhood: str = Field(default="", max_length=128)
    display_name: str = Field(default="", max_length=512)
    source: str = Field(default="osm", max_length=32)

    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    fetched_at: datetime = Field(
        default_factory=utcnow, sa_column=timestamp_column(index=True)
    )


def grid_key(latitude: float, longitude: float) -> str:
    """Stable cache key: digest of the coordinate snapped to the grid."""
    row = round(latitude / GRID_DEGREES)
    column = round(longitude / GRID_DEGREES)
    return hashlib.sha256(f"{row}:{column}".encode()).hexdigest()[:32]


def grid_center(latitude: float, longitude: float) -> tuple[float, float]:
    """Centre of the cell the coordinate falls into."""
    step = GRID_DEGREES
    return round(latitude / step) * step, round(longitude / step) * step