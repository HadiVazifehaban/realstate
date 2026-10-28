"""``PropertyMedia`` -- local/cloud media vault entries for a property."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import SQLModel, Field, Column

from app.models.base import pg_enum, timestamp_column, utcnow, uuid_column
from app.models.enums import MediaSyncStatus, MediaType

_TypeCol = Column(pg_enum(MediaType, "media_type"), nullable=False)
_SyncCol = Column(
    pg_enum(MediaSyncStatus, "media_sync_status"),
    nullable=False,
    index=True,
    default=MediaSyncStatus.LOCAL_ONLY,
)


class PropertyMedia(SQLModel, table=True):
    """One image/video/floor-plan attached to a property."""

    __tablename__ = "property_media"
    __table_args__ = (UniqueConstraint("property_id", "id", name="uq_property_media_property_pair"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    property_id: uuid.UUID = Field(foreign_key="property.id", index=True)

    media_type: MediaType = Field(default=MediaType.IMAGE, sa_column=_TypeCol)

    # Fast LAN-served, WebP/H.264-optimised file on the office machine.
    local_path: str | None = Field(default=None, max_length=1024)
    # S3 object URL in the AVG cloud (only set once shared to the MLS).
    cloud_url: str | None = Field(default=None, max_length=2048)

    sync_status: MediaSyncStatus = Field(default=MediaSyncStatus.LOCAL_ONLY, sa_column=_SyncCol)

    is_cover: bool = Field(default=False, index=True)
    sort_order: int = Field(default=0)

    original_filename: str | None = Field(default=None, max_length=255)
    mime_type: str = Field(default="image/webp", max_length=64)
    width: int | None = Field(default=None)
    height: int | None = Field(default=None)
    size_bytes: int | None = Field(default=None)
    checksum: str | None = Field(default=None, max_length=128)

    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
