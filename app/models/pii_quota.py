"""Daily PII reveal quota per agent (SaaS tiering, Phase 5).

Every successful owner-phone reveal decrements this row and writes an
``OwnerAccessLog`` entry, so quota spend and the audit trail can never drift
apart. ``day`` is a UTC date: the quota resets at midnight UTC.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Column
from sqlmodel import SQLModel, Field, UniqueConstraint

from app.models.base import pg_enum, timestamp_column, utcnow, uuid_column
from app.models.enums import SaasTier


class PiiQuota(SQLModel, table=True):
    """One row per (user, day) — the consumed counter for that day."""

    __tablename__ = "pii_quota"
    __table_args__ = (
        # Re-decrypting on the same day must update the existing row rather than
        # insert a second one, otherwise the counter resets and the tier cap
        # is silently bypassed.
        UniqueConstraint("user_id", "day", name="uq_pii_quota_user_day"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    user_id: uuid.UUID = Field(foreign_key="agency_user.id", index=True)
    day: date = Field(index=True)

    tier: SaasTier = Field(
        default=SaasTier.FREE,
        sa_column=Column(pg_enum(SaasTier, "saas_tier"), nullable=False),
    )
    consumed: int = Field(default=0, description="شمارش مصرف‌شده امروز")

    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
