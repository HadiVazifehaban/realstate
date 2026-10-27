"""Schemas for the Phase 5 CRM pipeline and the quota-gated PII vault.

Note the absence of any ``visit_date``: a visit is an appointment, and it is
modelled as ``LeadInteractionRequest`` with ``scheduled_at``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    InteractionType,
    LeadPriority,
    LeadStage,
    PropertySource,
    SaasTier,
    UserRole,
)


class LeadSummary(BaseModel):
    """Board card. Carries no owner PII — the phone needs a vault reveal."""

    id: uuid.UUID
    property_id: uuid.UUID
    agency_id: str = "local"
    stage: LeadStage
    priority: LeadPriority
    assigned_user_id: uuid.UUID | None = None
    assigned_subject: str | None = None
    is_bargain: bool = False
    deviation_pct: float | None = None
    neighborhood: str = ""
    city: str = ""
    title: str = ""
    total_price: int | None = None
    area: float | None = None
    rooms: int | None = None
    updated_at: datetime
    #: Listing provenance, so the board card can show owner / agent / portal
    #: without a second request. Optional for older serialized leads.
    source: PropertySource | None = None


class LeadListResponse(BaseModel):
    count: int
    items: list[LeadSummary]


class StageChangeRequest(BaseModel):
    """Move a card to the next column."""

    target_stage: LeadStage
    note: str = Field(default="", max_length=500)


class LeadCreateRequest(BaseModel):
    """Open a lead for an existing listing.

    Deliberately thin: a lead is a *view of a property*, not a second copy of
    it. Accepting a title or a price here would let the two drift, so the card
    always reads the price and specs off the linked listing.
    """

    property_id: uuid.UUID
    #: Who the desk should attribute the card to. Defaults to the calling
    #: principal when omitted, so the common case is a bare property id.
    assigned_user_id: uuid.UUID | None = None
    assigned_user_subject: str | None = Field(default=None, min_length=1, max_length=255)


class LeadCreateResponse(BaseModel):
    """Result of opening a lead.

    ``created=false`` means the listing already had a card -- the endpoint is
    idempotent per property, so a double-click cannot stack two cards.
    """

    lead_id: uuid.UUID
    created: bool
    stage: LeadStage = LeadStage.NEW_FILE


class LeadDeleteRequest(BaseModel):
    """Permanently purge a lead and its timeline.

    Carries a required ``confirm`` flag rather than being a bare DELETE so a
    mis-routed HTTP client cannot destroy deal history by accident -- the UI
    sends it only after an explicit second confirmation.
    """

    confirm: bool = Field(description="must be true; guards against stray deletes")


class LeadDeleteResponse(BaseModel):
    """What the purge actually removed, for the audit trail."""

    lead_id: uuid.UUID
    deleted_interactions: int


class InteractionRequest(BaseModel):
    """Append a timeline event.

    ``scheduled_at`` is required for ``VISIT_EVENT`` and rejected otherwise, so
    an appointment can never be recorded as a bare note.
    """

    interaction_type: InteractionType
    scheduled_at: datetime | None = None
    note: str = Field(default="", max_length=2000)


class InteractionResponse(BaseModel):
    id: uuid.UUID
    interaction_type: InteractionType
    scheduled_at: datetime | None = None
    note: str | None = None
    created_at: datetime


class LeadDetailResponse(BaseModel):
    """One lead plus its full timeline, newest event first."""

    lead: LeadSummary
    timeline: list[InteractionResponse]


class StageStat(BaseModel):
    """One column of the board header: depth and value."""

    stage: LeadStage
    count: int = 0
    total_value: int = 0


class BoardStatsResponse(BaseModel):
    """Desk totals for the kanban header.

    Aggregated server-side over every lead, not over the card page the board
    happens to have loaded, so the header cannot disagree with the archive.
    """

    total: int = 0
    #: The five live columns in board order; the archive is reported separately.
    columns: list[StageStat] = Field(default_factory=list)
    lost: int = 0
    bargains: int = 0
    open_value: int = 0
    closed_value: int = 0
    #: Won / (won + lost), as a percentage. Deals still in play are excluded.
    conversion_pct: float = 0.0


class QuotaStatusResponse(BaseModel):
    """Quota banner shown on the desk."""

    tier: SaasTier
    remaining: int | None = Field(
        description="سهمیهٔ باقی‌مانده؛ null یعنی نامحدود"
    )


class PiiRevealRequest(BaseModel):
    """Justification recorded alongside every reveal in the audit trail."""

    reason: str = Field(default="", max_length=255)


class PiiRevealResponse(BaseModel):
    """The only shape in which a plaintext owner phone ever leaves the vault."""

    property_id: uuid.UUID
    owner_name: str | None = None
    owner_phone: str | None = None
    tier: SaasTier
    remaining_quota: int | None = None
    audit_logged: bool = True


class PiiAccessLogEntry(BaseModel):
    """Supervisor view of the vault audit trail."""

    id: uuid.UUID
    user_id: uuid.UUID | None = None
    property_id: uuid.UUID | None = None
    action: str
    allowed: bool
    reason: str = ""
    client_ip: str = ""
    created_at: datetime
