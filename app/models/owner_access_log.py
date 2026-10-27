"""Access audit trail for the encrypted owner PII vault (Zero-Trust policy)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import SQLModel, Field

from app.models.base import timestamp_column, utcnow, uuid_column


class OwnerAccessLog(SQLModel, table=True):
    """Immutable record of every owner-PII access attempt."""

    __tablename__ = "owner_access_log"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    pii_id: uuid.UUID | None = Field(default=None, foreign_key="property_owner_pii.id", index=True)
    property_id: uuid.UUID | None = Field(default=None, foreign_key="property.id", index=True)
    agency_id: uuid.UUID | None = Field(default=None, foreign_key="agency.id", index=True)
    user_id: uuid.UUID | None = Field(default=None, foreign_key="agency_user.id", index=True)

    action: str = Field(default="READ", max_length=32, description="READ / WRITE / EXPORT")
    allowed: bool = Field(default=True)
    reason: str = Field(default="", max_length=255)
    client_ip: str = Field(default="", max_length=64)

    created_at: datetime = Field(
        default_factory=utcnow, sa_column=timestamp_column(index=True)
    )
