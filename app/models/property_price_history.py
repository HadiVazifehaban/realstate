"""``PropertyPriceHistory`` -- append-only price timeline per property.

Phase 3b: every price change discovered by ingestion, by an advisor edit or by
the automated valuation engine is recorded here with its origin, so a price drop
("bargain") can be surfaced to the agent desk.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM as PostgreSQLEnum
from sqlmodel import SQLModel, Field

from app.models.base import pg_enum, timestamp_column, utcnow, uuid_column
from app.models.enums import PriceChangeSource


class PropertyPriceHistory(SQLModel, table=True):
    """One row per observed price of a property."""

    __tablename__ = "property_price_history"
    __table_args__ = (
        # Re-ingesting the same listing must not append the same price twice.
        UniqueConstraint("property_id", "new_price", "source", name="uq_price_history_row"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    property_id: uuid.UUID = Field(foreign_key="property.id", index=True)

    previous_price: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    new_price: int = Field(sa_column=Column(BigInteger, nullable=False))
    price_difference: int = Field(sa_column=Column(BigInteger, nullable=False))
    change_percentage: float = Field(default=0.0, description="درصد تغییر نسبت به قیمت قبلی")

    source: PriceChangeSource = Field(
        default=PriceChangeSource.SCRAPER,
        sa_column=Column(
            PostgreSQLEnum(
                PriceChangeSource,
                name="price_source",
                values_callable=lambda members: [member.value for member in members],
                create_type=False,
                validate_strings=True,
            ),
            nullable=False,
        ),
    )
    source_ref: str | None = Field(default=None, max_length=128)
    created_by_id: uuid.UUID | None = Field(default=None, foreign_key="agency_user.id")
    recorded_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column(index=True))
