"""Per-user preferences (active city and future UI settings).

Keyed by the Keycloak ``sub`` (``principal.subject``), NOT by username: a
username can be renamed in the realm while the subject stays stable.  In
LICENSE (offline) mode every caller shares the bootstrap subject, so the row
is effectively node-wide -- which is the correct semantic for one office.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.base import timestamp_column, utcnow, uuid_column


class UserPreference(SQLModel, table=True):
    """One preference row per (subject, key)."""

    __tablename__ = "user_preference"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    subject: str = Field(index=True, max_length=256)
    key: str = Field(index=True, max_length=64)
    value: str = Field(default="", max_length=512)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
