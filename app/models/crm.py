"""Phase 5 CRM models: the five-column lead pipeline and its event timeline.

A lead is a *property being worked by the desk*. The appointment timestamp for
a site visit lives here and only here — on ``LeadInteraction.scheduled_at`` with
``interaction_type = VISIT_EVENT``. There is deliberately no ``visit_date``
column anywhere in this schema.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Text
from sqlmodel import SQLModel, Column, Field

from app.models.base import pg_enum, timestamp_column, utcnow, uuid_column
from app.models.enums import InteractionType, LeadPriority, LeadStage


class CrmLead(SQLModel, table=True):
    """One lead on the broker desk, derived from a canonical property."""

    __tablename__ = "crm_lead"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    property_id: uuid.UUID = Field(foreign_key="property.id", index=True)

    assigned_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="agency_user.id", index=True
    )

    stage: LeadStage = Field(
        default=LeadStage.NEW_FILE,
        sa_column=Column(
            pg_enum(LeadStage, "lead_stage"), nullable=False, index=True
        ),
    )
    priority: LeadPriority = Field(
        default=LeadPriority.NORMAL,
        sa_column=Column(pg_enum(LeadPriority, "lead_priority"), nullable=False),
    )

    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    # -- Denormalised snapshot of the property's verdict at dispatch time ------
    # Kept so the desk can sort/filter on bargain without joining `property`
    # on every render; refreshed whenever the valuation engine re-scores.
    is_bargain: bool = Field(default=False, index=True)
    deviation_pct: float | None = Field(default=None)
    neighborhood: str = Field(default="", max_length=128, index=True)
    city: str = Field(default="", max_length=64)

    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class LeadInteraction(SQLModel, table=True):
    """Append-only CRM timeline event for one lead.

    ``scheduled_at`` is the appointment time for a ``VISIT_EVENT``; it is an
    interaction record, never a property attribute.
    """

    __tablename__ = "lead_interaction"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    lead_id: uuid.UUID = Field(foreign_key="crm_lead.id", index=True)
    actor_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="agency_user.id", index=True
    )

    interaction_type: InteractionType = Field(
        sa_column=pg_enum(InteractionType, "interaction_type")
    )
    scheduled_at: datetime | None = Field(
        default=None, sa_column=timestamp_column(nullable=True, index=True)
    )
    note: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
