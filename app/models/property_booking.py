"""``PropertyVisitBooking`` -- the calendar slot behind the visit scheduler.

One booked appointment on one listing. This is the single source of truth for
what happens at a given date/time: the scheduler widget renders slots against
this table, the calendar task engine drives notifications from it, and the CRM
timeline keeps a chronological log of the event instead of re-declaring the
schedule inside the property row.

The listing itself never carries a visit timestamp (see
``app/models/enums.py`` and the `UnifiedListingSchema` readme). The only
``visit_date`` anywhere on the surface is the one in this booking table.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Self

from sqlalchemy import Date, Text, Time, UniqueConstraint
from sqlmodel import SQLModel, Field, Column, Relationship, Integer

from app.models.base import pg_enum, timestamp_column, utcnow, uuid_column
from app.models.enums import VisitSlotKind, VisitSlotStatus
from app.models.property import Property


class PropertyVisitBooking(SQLModel, table=True):
    """One calendared appointment on a single listing.

    A booking is a *place* in the property's schedule. It owns the date, the
    clock window and the lifecycle state, and it is what the scheduler widget
    renders as available, taken or up-for-cancellation. The listing row itself
    never records a visit timestamp.
    """

    __tablename__ = "property_visit_booking"

    __table_args__ = (
        UniqueConstraint(
            "property_id",
            "slot_date",
            "start_time",
            name="uq_property_visit_booking_slot",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())

    # -- Foreign keys ----------------------------------------------------------

    property_id: uuid.UUID = Field(
        foreign_key="property.id", index=True, nullable=False
    )
    property: Property = Relationship(back_populates="visit_bookings")

    created_by_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="agency_user.id", index=True
    )

    # -- Calendar fields -------------------------------------------------------

    slot_date: date = Field(
        sa_column=Column(Date, nullable=False, index=True),
    )
    start_time: time = Field(
        sa_column=Column(Time, nullable=False, index=True),
    )
    end_time: time | None = Field(
        sa_column=Column(Time, nullable=True, index=True),
    )

    # -- Lifecycle -------------------------------------------------------------

    status: VisitSlotStatus = Field(
        sa_column=Column(
            pg_enum(VisitSlotStatus, "visit_slot_status"),
            nullable=False,
            index=True,
        ),
        default=VisitSlotStatus.REQUESTED,
    )
    kind: VisitSlotKind = Field(
        sa_column=Column(
            pg_enum(VisitSlotKind, "visit_slot_kind"),
            nullable=False,
        ),
    )

    # -- Guest / note ----------------------------------------------------------

    guests: int | None = Field(
        default=None, ge=1, sa_column=Column(Integer, nullable=True)
    )
    notes: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )

    # -- Timestamps ------------------------------------------------------------

    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())

    def __repr__(self) -> str:
        return (
            f"<PropertyVisitBooking(id={self.id!r}, property_id={self.property_id!r}, "
            f"date={self.slot_date!r}, start={self.start_time!r}, "
            f"status={self.status!r})>"
        )

    @classmethod
    def draft_for(
        cls,
        property_id: uuid.UUID,
        slot_date: date,
        start_time: time,
        end_time: time,
        *,
        kind: VisitSlotKind = VisitSlotKind.OFFICE_HOUSE,
    ) -> Self:
        """Build a DRAFT booking the desk can edit/confirm without advertising it."""
        return cls(
            property_id=property_id,
            slot_date=slot_date,
            start_time=start_time,
            end_time=end_time,
            kind=kind,
            status=VisitSlotStatus.DRAFT,
        )
