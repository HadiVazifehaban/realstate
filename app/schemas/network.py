"""Schemas for the inter-agency collaboration network (Phase 1)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AgencyStatus,
    AuditAction,
    CommissionModel,
    CommissionStatus,
    CooperationScope,
    CooperationStatus,
    DisputeCategory,
    DisputeStatus,
    ListingShareMode,
    ReferralStatus,
    ShareStatus,
    TransferStatus,
)


# --------------------------------------------------------------------------- #
# Offices
# --------------------------------------------------------------------------- #
class AgencyCreate(BaseModel):
    """Register an office on the network."""

    slug: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=2, max_length=255)
    name_fa: str = Field(default="", max_length=255)
    city: str = Field(default="", max_length=64)
    district: str = Field(default="", max_length=64)
    phone: str = Field(default="", max_length=32)
    description: str = Field(default="", max_length=2000)
    referral_code: str = Field(default="", max_length=16)


class AgencyReviewIn(BaseModel):
    """Administrative decision on a pending office application."""

    decision: str = Field(pattern=r"^(APPROVE|REJECT)$")
    reason: str = Field(default="", max_length=1000)


class AgencyRead(BaseModel):
    """An office as a partner sees it.

    The settlement IBAN is deliberately absent here even though the model has
    one: a *counterparty's* bank details belong to a commission ledger at
    settlement time, not to a directory listing anybody with a token can read.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    name_fa: str
    city: str
    district: str
    phone: str
    logo_url: str
    description: str
    status: AgencyStatus
    display_name: str
    created_at: datetime


class WorkspaceRead(BaseModel):
    """An office the authenticated subject is actively a member of."""

    id: uuid.UUID
    slug: str
    name: str
    name_fa: str
    status: AgencyStatus
    role: str


# --------------------------------------------------------------------------- #
# Cooperation requests
# --------------------------------------------------------------------------- #
class CooperationCreate(BaseModel):
    """A request to work with another office."""

    requester_agency_id: uuid.UUID
    target_agency_id: uuid.UUID
    # Validated against the enum by the route, so a bad value is a 422 from the
    # endpoint that knows what "REQUESTED" means rather than from the model.
    scope: str = Field(default=CooperationScope.SHARE_LISTINGS.value)
    # 0..100. 50 here is the co-broke convention (office that owns the file and
    # office that brings the buyer split the commission evenly), not a
    # suggestion that 50 is always right.
    default_commission_pct: int = Field(default=50, ge=0, le=100)
    # Days until the request lapses. None means "no expiry": an open request
    # that never dies is how an office ends up working with a partner that
    # stopped answering a year ago, so the UI offers expiry presets.
    expires_in_days: int | None = Field(default=30, ge=1, le=3650)


class CooperationDecision(BaseModel):
    """Approve or reject a request."""

    granted_scopes: list[str] = Field(default_factory=list)
    reason: str = Field(default="", max_length=1000)


class CooperationRead(BaseModel):
    """One cooperation request, as either side sees it."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requester_agency_id: uuid.UUID
    target_agency_id: uuid.UUID
    status: CooperationStatus = CooperationStatus.PENDING
    scope: CooperationScope = CooperationScope.SHARE_LISTINGS
    granted_scope_list: list[CooperationScope] = Field(default_factory=list)
    default_commission_pct: int = 50
    expires_at: datetime | None = None
    decided_at: datetime | None = None
    decision_reason: str = ""
    requested_by: str = ""
    decided_by: str = ""
    created_at: datetime



# --------------------------------------------------------------------------- #
# Listing shares (Phase 2)
# --------------------------------------------------------------------------- #
class SharePermissionInput(BaseModel):
    """The permission matrix a share is created with.

    Every field defaults to the *safe* end -- owner phone off, exact address
    off, re-share off, export off -- so a caller that forgets a field gets a
    restrictive share, never an over-permissive one (Section F).
    """

    view_summary: bool = True
    view_full_details: bool = False
    show_owner_phone: bool = False
    show_exact_address: bool = False
    allow_notes: bool = False
    allow_visit_request: bool = False
    allow_negotiation: bool = False
    allow_export: bool = False
    allow_re_share: bool = False


class SharePermissionRead(SharePermissionInput):
    updated_at: datetime
    updated_by: str


class ListingShareCreate(BaseModel):
    """Share / refer / transfer a file to a partner office.

    ``mode`` is validated by the route against ``ListingShareMode`` so a bad
    value is a 422 that names the operation, not a silent default to SHARE.
    """

    property_id: uuid.UUID
    source_agency_id: uuid.UUID
    target_agency_id: uuid.UUID
    mode: str = Field(default=ListingShareMode.SHARE.value)
    target_agent: str = Field(default="", max_length=255)
    note: str = Field(default="", max_length=2000)
    internal_note: str = Field(default="", max_length=2000)
    # Days until the share lapses; None means no expiry.
    expires_in_days: int | None = Field(default=30, ge=1, le=3650)
    permissions: SharePermissionInput = Field(default_factory=SharePermissionInput)


class ListingShareRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    property_id: uuid.UUID
    source_agency_id: uuid.UUID
    target_agency_id: uuid.UUID
    mode: ListingShareMode
    status: ShareStatus
    target_agent: str
    note: str
    expires_at: datetime | None
    created_by: str
    created_at: datetime
    revoked_at: datetime | None
    # The private note is deliberately NOT exposed across the boundary.


class ListingShareDetailRead(ListingShareRead):
    internal_note: str
    permissions: SharePermissionRead


# --------------------------------------------------------------------------- #
# Referrals (Phase 3)
# --------------------------------------------------------------------------- #
class LeadReferralCreate(BaseModel):
    subject: str = Field(min_length=2, max_length=255)
    client_masked: str = Field(default="", max_length=255)
    source_agency_id: uuid.UUID
    target_agency_id: uuid.UUID
    property_id: uuid.UUID | None = None
    assigned_to: str = Field(default="", max_length=255)
    referral_fee_pct: int = Field(default=0, ge=0, le=100)
    note: str = Field(default="", max_length=2000)


class LeadReferralRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject: str
    client_masked: str
    source_agency_id: uuid.UUID
    target_agency_id: uuid.UUID
    property_id: uuid.UUID | None
    assigned_to: str
    referral_fee_pct: int
    stage: ReferralStatus
    note: str
    outcome: str
    created_at: datetime
    updated_at: datetime


class ReferralStageUpdate(BaseModel):
    stage: str
    outcome: str = Field(default="", max_length=1000)


# --------------------------------------------------------------------------- #
# Transfers (Phase 3)
# --------------------------------------------------------------------------- #
class ListingTransferCreate(BaseModel):
    """Move a file's responsibility to another office.

    A transfer is a high-sensitivity operation, so it carries a mandatory
    ``reason`` and an explicit ``confirm`` flag -- the route rejects a transfer
    without both, which is what keeps it from looking like a casual share.
    """

    property_id: uuid.UUID
    from_agency_id: uuid.UUID
    to_agency_id: uuid.UUID
    to_user: str = Field(default="", max_length=255)
    reason: str = Field(min_length=3, max_length=1000)
    residual_commission_pct: int = Field(default=0, ge=0, le=100)
    confirm: bool = False


class ListingTransferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    property_id: uuid.UUID
    from_agency_id: uuid.UUID
    to_agency_id: uuid.UUID
    from_user: str
    to_user: str
    status: TransferStatus
    reason: str
    residual_commission_pct: int
    executed_by: str
    executed_at: datetime | None
    created_at: datetime


# --------------------------------------------------------------------------- #
# Commissions (Phase 4)
# --------------------------------------------------------------------------- #
class CommissionAllocationInput(BaseModel):
    agency_id: uuid.UUID | None = None
    agent: str = Field(default="", max_length=255)
    percent: int = Field(default=0, ge=0, le=100)
    fixed_amount: int = Field(default=0, ge=0)


class CommissionAgreementCreate(BaseModel):
    property_id: uuid.UUID | None = None
    source_agency_id: uuid.UUID
    target_agency_id: uuid.UUID
    model: str = Field(default=CommissionModel.PERCENTAGE.value)
    basis_amount: int = Field(default=0, ge=0)
    currency: str = Field(default="IRR", max_length=8)
    note: str = Field(default="", max_length=2000)
    allocations: list[CommissionAllocationInput] = Field(default_factory=list)


class CommissionAllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID | None
    agent: str
    percent: int
    fixed_amount: int


class CommissionPaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    allocation_id: uuid.UUID
    amount: int
    reference: str
    note: str
    recorded_by: str
    recorded_at: datetime


class CommissionAgreementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    property_id: uuid.UUID | None
    source_agency_id: uuid.UUID
    target_agency_id: uuid.UUID
    model: CommissionModel
    status: CommissionStatus
    basis_amount: int
    currency: str
    note: str
    locked_by: str
    locked_at: datetime | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class CommissionAgreementDetailRead(CommissionAgreementRead):
    allocations: list[CommissionAllocationRead]
    payments: list[CommissionPaymentRead]
    # Rolled-up so the ledger header needs no client-side summation.
    total_paid: int
    remaining: int


class CommissionPaymentCreate(BaseModel):
    allocation_id: uuid.UUID
    amount: int = Field(gt=0)
    reference: str = Field(default="", max_length=255)
    note: str = Field(default="", max_length=1000)


# --------------------------------------------------------------------------- #
# Disputes (Phase 5)
# --------------------------------------------------------------------------- #
class DisputeCreate(BaseModel):
    category: str
    claimant_agency_id: uuid.UUID
    respondent_agency_id: uuid.UUID
    share_id: uuid.UUID | None = None
    agreement_id: uuid.UUID | None = None
    referral_id: uuid.UUID | None = None
    property_id: uuid.UUID | None = None
    title: str = Field(min_length=3, max_length=255)
    detail: str = Field(default="", max_length=4000)


class DisputeMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    is_internal: bool = False


class DisputeMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author: str
    body: str
    is_internal: bool
    created_at: datetime


class DisputeStatusUpdate(BaseModel):
    status: str
    resolution: str = Field(default="", max_length=4000)


class DisputeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: DisputeCategory
    status: DisputeStatus
    claimant_agency_id: uuid.UUID
    respondent_agency_id: uuid.UUID
    share_id: uuid.UUID | None
    agreement_id: uuid.UUID | None
    referral_id: uuid.UUID | None
    property_id: uuid.UUID | None
    title: str
    detail: str
    resolution: str
    opened_by: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class DisputeDetailRead(DisputeRead):
    messages: list[DisputeMessageRead]


# --------------------------------------------------------------------------- #
# Audit (Phase 5)
# --------------------------------------------------------------------------- #
class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: AuditAction
    actor: str
    actor_agency_id: uuid.UUID | None
    entity_type: str
    entity_id: uuid.UUID | None
    property_id: uuid.UUID | None
    target_agency_id: uuid.UUID | None
    detail: str
    created_at: datetime


# --------------------------------------------------------------------------- #
# Overview & reports (dashboard aggregations)
# --------------------------------------------------------------------------- #
class NetworkOverviewRead(BaseModel):
    """سرجمع داشبورد شبکه — شمارش هر منو برای کارت‌های صفحه اصلی."""

    agencies_total: int = 0
    agencies_verified: int = 0
    cooperations_pending: int = 0
    cooperations_approved: int = 0
    shares_active: int = 0
    shares_total: int = 0
    referrals_open: int = 0
    referrals_converted: int = 0
    transfers_total: int = 0
    commissions_open: int = 0
    commissions_basis_total: int = 0
    commissions_paid_total: int = 0
    disputes_open: int = 0
    audit_total: int = 0


class ReportsByStatus(BaseModel):
    status: str
    label_fa: str = ""
    count: int = 0


class NetworkReportsRead(BaseModel):
    """داده گزارش‌های همکاری — توزیع وضعیت‌ها + سرجمع مالی."""

    shares_by_status: list[ReportsByStatus] = Field(default_factory=list)
    referrals_by_stage: list[ReportsByStatus] = Field(default_factory=list)
    transfers_by_status: list[ReportsByStatus] = Field(default_factory=list)
    commissions_by_status: list[ReportsByStatus] = Field(default_factory=list)
    disputes_by_status: list[ReportsByStatus] = Field(default_factory=list)
    cooperations_by_status: list[ReportsByStatus] = Field(default_factory=list)
    audit_by_action: list[ReportsByStatus] = Field(default_factory=list)
    total_basis: int = 0
    total_paid: int = 0
    total_remaining: int = 0
    conversion_rate_pct: int = 0
