"""``PropertyReport`` -- a "this listing is wrong" report.

Exists so the report block on the detail page has somewhere to land. Reports are
kept even if the reporter's account disappears: the abuse team only needs enough
to answer an email, and a report that vanishes with its author is worthless
evidence.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, Text
from sqlmodel import SQLModel, Field

from app.models.base import timestamp_column, utcnow, uuid_column


class ReportReason:
    """The reasons the detail page offers.

    Kept as plain strings rather than a database enum: abuse categories get
    revised more often than they get used in queries, and a hard enum would mean
    a migration every time the copy changes.
    """

    WRONG_PRICE = "wrong_price"
    OUTDATED = "outdated"
    DUPLICATE = "duplicate"
    MISLEADING = "misleading"
    FRAUD = "fraud"
    OTHER = "other"

    ALL = (
        WRONG_PRICE,
        OUTDATED,
        DUPLICATE,
        MISLEADING,
        FRAUD,
        OTHER,
    )


class PropertyReport(SQLModel, table=True):
    """One abuse/accuracy report against a listing."""

    __tablename__ = "property_report"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    property_id: uuid.UUID = Field(foreign_key="property.id", index=True)

    reason: str = Field(max_length=64)
    detail: str | None = Field(
        default=None,
        sa_column=Column(Text().with_variant(Text(), "sqlite"), nullable=True),
    )
    reporter_email: str | None = Field(default=None, max_length=255)

    created_at: datetime = Field(
        default_factory=utcnow, sa_column=timestamp_column()
    )