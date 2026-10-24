"""Reusable SQL/GeoAlchemy column helpers for the SQLModel layer."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Enum as SAEnum
from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import mapped_column
from sqlmodel import Column, Field


def utcnow() -> datetime:
    """Timezone-aware UTC 'now' used for all timestamps."""
    return datetime.now(timezone.utc)


def pg_enum(enum_cls: type[Enum], name: str) -> SAEnum:
    """Create a PostgreSQL enum that stores member *values* (not names)."""
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda members: [m.value for m in members],
        native_enum=True,
        validate_strings=True,
    )


def uuid_column(primary_key: bool = True) -> Any:
    """UUID primary-key column backed by the native ``uuid`` type."""
    return Column(
        Uuid(as_uuid=True),
        primary_key=primary_key,
        default=uuid.uuid4,
        nullable=False,
    )


def timestamp_column(*, nullable: bool = False, index: bool = False) -> Any:
    """Timezone-aware timestamp column."""
    return Column(DateTime(timezone=True), nullable=nullable, index=index)


def point_column(nullable: bool = True) -> Column:
    """EPSG:4326 POINT geometry (property location)."""
    return Column(Geometry(geometry_type="POINT", srid=4326), nullable=nullable)


def polygon_column(nullable: bool = True) -> Column:
    """EPSG:4326 POLYGON geometry (client target area)."""
    return Column(Geometry(geometry_type="POLYGON", srid=4326), nullable=nullable)


__all__ = [
    "utcnow",
    "pg_enum",
    "uuid_column",
    "timestamp_column",
    "point_column",
    "polygon_column",
    "Field",
    "mapped_column",
]
