"""Inter-agency collaboration: shares, referrals, transfers, commissions,
disputes and the audit trail (شبکه همکاری دفاتر — Phases 2-5).

Phase 1 (``agency_network.py``) gave us offices and the *right* to work
together. This module is everything that happens *inside* a relationship once
two offices actually share a file:

* a **ListingShare** is access to one file. Its permission matrix is the row of
  booleans that decides what the partner office may see and do -- never the
  relationship scope, which is the coarse "may we work together" switch.
* a **LeadReferral** hands a client over without moving the file. Referrals are
  deliberately their own table: conflating a referral with a share is how an MLS
  loses track of who owns a lead.
* a **ListingTransferHistory** row is the immutable record that responsibility
  for a file moved. Every transfer appends; nothing is overwritten.
* **CommissionAgreement/Allocation/Payment** are the money. An agreement is
  versioned by ``LOCKED`` -- once locked, a split changes only through a new
  allocation row, so "who agreed to what, and when" stays answerable.
* **DisputeCase/DisputeMessage** and **AuditEvent** close the loop: every
  security-sensitive action (reveal, export, permission change, transfer,
  commission edit) writes an AuditEvent, and a dispute links back to the very
  events it is about.

Three rules hold the whole module together and are worth stating because
breaking any one of them makes the network unauditable:

* sharing, transferring and referring are **different operations** with
  different tables.
* ownership history is **append-only**.
* every cross-office action records **actor + target + timestamp**.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger
from sqlmodel import Column, Field, SQLModel
from app.models.base import pg_enum, timestamp_column, utcnow, uuid_column
from app.models.enums import (
    AuditAction,
    CommissionModel,
    CommissionStatus,
    DisputeCategory,
    DisputeStatus,
    ListingShareMode,
    ReferralStatus,
    ShareStatus,
    TransferStatus,
)

_ModeCol = Column(pg_enum(ListingShareMode, "share_mode"), nullable=False, default=ListingShareMode.SHARE)
_ShareStatusCol = Column(pg_enum(ShareStatus, "share_status"), nullable=False, default=ShareStatus.ACTIVE)
_ReferralStatusCol = Column(pg_enum(ReferralStatus, "referral_status"), nullable=False, default=ReferralStatus.SENT)
_TransferStatusCol = Column(pg_enum(TransferStatus, "transfer_status"), nullable=False, default=TransferStatus.PENDING)
_CommModelCol = Column(pg_enum(CommissionModel, "commission_model"), nullable=False, default=CommissionModel.PERCENTAGE)
_CommStatusCol = Column(pg_enum(CommissionStatus, "commission_status"), nullable=False, default=CommissionStatus.DRAFT)
_DisputeCategoryCol = Column(pg_enum(DisputeCategory, "dispute_category"), nullable=False)
_DisputeStatusCol = Column(pg_enum(DisputeStatus, "dispute_status"), nullable=False, default=DisputeStatus.OPEN)
_AuditActionCol = Column(pg_enum(AuditAction, "audit_action"), nullable=False)


class ListingShare(SQLModel, table=True):
    """One office sharing (or transferring, or referring) one file to another.

    The grant itself. ``mode`` says which of the three operations this is, and
    the companion ``ListingSharePermission`` holds the fine-grained booleans.
    A share points at a *property* by id rather than a FK so a deleted listing
    does not cascade the collaboration history away.
    """

    __tablename__ = "listing_share"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())

    property_id: uuid.UUID = Field(index=True, description="فایل/آگهی مشترک‌شده")
    # The owner office and the recipient office. Two columns, not one "other
    # office": an outgoing and an incoming share are the same row seen from
    # either end, and "who shared with whom" must not depend on where you sit.
    source_agency_id: uuid.UUID = Field(index=True, description="دفتر مالک")
    target_agency_id: uuid.UUID = Field(index=True, description="دفتر همکار")

    mode: ListingShareMode = Field(default=ListingShareMode.SHARE, sa_column=_ModeCol)
    status: ShareStatus = Field(default=ShareStatus.ACTIVE, sa_column=_ShareStatusCol)

    # Optional: a share may name a specific recipient agent rather than the
    # whole partner office. Blank means "the office".
    target_agent: str = Field(default="", max_length=255, description="username")

    # Collaboration note visible to both offices, and a private note that must
    # never cross the boundary -- the owner's internal reasoning about the file.
    note: str = Field(default="", max_length=2000)
    internal_note: str = Field(default="", max_length=2000)

    # Time-bounded access. ``expires_at`` is what makes "lend it for a week"
    # enforceable rather than a promise; None means no expiry.
    expires_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))

    created_by: str = Field(default="", max_length=255, description="username")
    revoked_by: str = Field(default="", max_length=255, description="username")
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    revoked_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))

    # ---- Permission matrix defaults are DENY. The permission row carries the
    # real booleans; these documented defaults are the ones the API applies when
    # a share is created, and they are deliberately the safe end of every switch:
    #   owner_phone -> OFF (masked)   exact_address -> OFF (hidden)
    #   re_share    -> OFF            export        -> OFF
    #   negotiate / visit -> OFF until explicitly granted


class ListingSharePermission(SQLModel, table=True):
    """The fine-grained booleans behind a share.

    Split out from ``ListingShare`` so tightening one permission is a single
    audited UPDATE (``PERMISSION_CHANGED``) rather than a rewrite of the whole
    grant, and so the defaults are unambiguous: every sensitive switch starts
    false and must be turned on deliberately (Section F).
    """

    __tablename__ = "listing_share_permission"

    share_id: uuid.UUID = Field(sa_column=uuid_column(primary_key=True))

    view_summary: bool = Field(default=True)
    view_full_details: bool = Field(default=False)
    # Sensitive reveals -- OFF by default.
    show_owner_phone: bool = Field(default=False)
    show_exact_address: bool = Field(default=False)
    # Actions the partner office may take.
    allow_notes: bool = Field(default=False)
    allow_visit_request: bool = Field(default=False)
    allow_negotiation: bool = Field(default=False)
    allow_export: bool = Field(default=False)
    # Re-share to a third office -- OFF by default.
    allow_re_share: bool = Field(default=False)

    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_by: str = Field(default="", max_length=255, description="username")


class LeadReferral(SQLModel, table=True):
    """A client hand-off between offices.

    Distinct from a share: the file stays with the referring office, and what
    travels is a *lead* plus an agreed referral fee. The client identity is
    masked on the referring side until the recipient accepts.
    """

    __tablename__ = "lead_referral"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())

    subject: str = Field(max_length=255)
    # Masked client identity carried across the boundary.
    client_masked: str = Field(default="", max_length=255)

    source_agency_id: uuid.UUID = Field(index=True, description="دفتر ارجاع‌کننده")
    target_agency_id: uuid.UUID = Field(index=True, description="دفتر گیرنده")
    # Optional link to the property or a cooperation the referral came from.
    property_id: uuid.UUID | None = Field(default=None, index=True)

    assigned_to: str = Field(default="", max_length=255, description="username در دفتر مقصد")
    referral_fee_pct: int = Field(default=0, ge=0, le=100)

    stage: ReferralStatus = Field(default=ReferralStatus.SENT, sa_column=_ReferralStatusCol)
    note: str = Field(default="", max_length=2000)
    outcome: str = Field(default="", max_length=1000)

    created_by: str = Field(default="", max_length=255, description="username")
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class ListingTransferHistory(SQLModel, table=True):
    """Immutable record that a file's responsibility moved between offices.

    Append-only by design: a re-transfer is a new row, so the chain of custody
    is a first-class question the model can answer. ``from``/``to`` agency ids
    plus the acting user and timestamp are the audit spine the prompt asks for.
    """

    __tablename__ = "listing_transfer_history"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())

    property_id: uuid.UUID = Field(index=True, description="فایل منتقل‌شده")
    from_agency_id: uuid.UUID = Field(index=True, description="دفتر مبدأ")
    to_agency_id: uuid.UUID = Field(index=True, description="دفتر مقصد")
    from_user: str = Field(default="", max_length=255, description="username مسئول قبلی")
    to_user: str = Field(default="", max_length=255, description="username مسئول جدید")

    status: TransferStatus = Field(default=TransferStatus.PENDING, sa_column=_TransferStatusCol)
    # A transfer asks *why*; a share does not have to.
    reason: str = Field(default="", max_length=1000)
    # Whether the previous office keeps a residual commission on future deals.
    residual_commission_pct: int = Field(default=0, ge=0, le=100)

    executed_by: str = Field(default="", max_length=255, description="username")
    executed_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class CommissionAgreement(SQLModel, table=True):
    """The agreed split for a co-broke deal.

    Version = lifecycle. A DRAFT agreement edits freely; the moment it is
    ``LOCKED`` the split is fixed and any change is a new amendment row, never
    an in-place edit -- which is exactly what stops a quiet commission rewrite
    during a dispute.
    """

    __tablename__ = "commission_agreement"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())

    property_id: uuid.UUID | None = Field(default=None, index=True)
    source_agency_id: uuid.UUID = Field(index=True, description="دفتر مالک فایل")
    target_agency_id: uuid.UUID = Field(index=True, description="دفتر همکار")

    model: CommissionModel = Field(default=CommissionModel.PERCENTAGE, sa_column=_CommModelCol)
    status: CommissionStatus = Field(default=CommissionStatus.DRAFT, sa_column=_CommStatusCol)

    # The basis the split applies to (e.g. deal price). Kept as an integer minor
    # unit to avoid float money; currency is the node default.
    basis_amount: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, default=0))
    currency: str = Field(default="IRR", max_length=8)

    note: str = Field(default="", max_length=2000)
    locked_by: str = Field(default="", max_length=255, description="username")
    locked_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))

    created_by: str = Field(default="", max_length=255, description="username")
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class CommissionAllocation(SQLModel, table=True):
    """One side's slice of an agreement -- by office and/or agent.

    Multiple rows per agreement, one per beneficiary. Summing allocations is
    what the commission editor validates against 100% (percent) or the basis
    (fixed).
    """

    __tablename__ = "commission_allocation"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())

    agreement_id: uuid.UUID = Field(index=True)
    agency_id: uuid.UUID | None = Field(default=None, index=True, description="دفتر ذی‌نفع")
    agent: str = Field(default="", max_length=255, description="username مشاور (اختیاری)")

    # Percent of the basis, or a fixed amount when the agreement model is FIXED.
    percent: int = Field(default=0, ge=0, le=100)
    fixed_amount: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, default=0))

    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class CommissionPayment(SQLModel, table=True):
    """A recorded payment against one allocation.

    Append-only ledger lines. An allocation is settled when the sum of its
    payments reaches its share; the agreement rolls up to PARTIALLY_PAID or
    SETTLED from here.
    """

    __tablename__ = "commission_payment"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())

    allocation_id: uuid.UUID = Field(index=True)
    amount: int = Field(sa_column=Column(BigInteger, nullable=False))
    # Reference to the off-ledger proof (receipt/transfer id), free text.
    reference: str = Field(default="", max_length=255)
    note: str = Field(default="", max_length=1000)

    recorded_by: str = Field(default="", max_length=255, description="username")
    recorded_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class DisputeCase(SQLModel, table=True):
    """A cross-office disagreement.

    Links to the entity it is about (a share, an agreement, a referral) by id
    rather than FK, so the dispute survives the underlying row's lifecycle and
    stays answerable after the fact.
    """

    __tablename__ = "dispute_case"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())

    category: DisputeCategory = Field(sa_column=_DisputeCategoryCol)
    status: DisputeStatus = Field(default=DisputeStatus.OPEN, sa_column=_DisputeStatusCol)

    claimant_agency_id: uuid.UUID = Field(index=True, description="دفتر شاکی")
    respondent_agency_id: uuid.UUID = Field(index=True, description="دفتر خوانده")

    # What it is about -- at most one is set, kept as separate optional ids so a
    # dispute can point at whichever entity it concerns.
    share_id: uuid.UUID | None = Field(default=None, index=True)
    agreement_id: uuid.UUID | None = Field(default=None, index=True)
    referral_id: uuid.UUID | None = Field(default=None, index=True)
    property_id: uuid.UUID | None = Field(default=None, index=True)

    title: str = Field(max_length=255)
    detail: str = Field(default="", max_length=4000)
    resolution: str = Field(default="", max_length=4000)

    opened_by: str = Field(default="", max_length=255, description="username")
    resolved_by: str = Field(default="", max_length=255, description="username")
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    resolved_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))


class DisputeMessage(SQLModel, table=True):
    """A message in a dispute thread. Append-only."""

    __tablename__ = "dispute_message"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())

    dispute_id: uuid.UUID = Field(index=True)
    author: str = Field(default="", max_length=255, description="username")
    body: str = Field(max_length=4000)
    is_internal: bool = Field(default=False, description="یادداشت داخلی شبکه، مرئی برای مدیر")
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class AuditEvent(SQLModel, table=True):
    """The security trail. Every sensitive network action writes one row.

    ``actor`` + ``target`` + ``action`` + ``timestamp`` is the spine the prompt
    requires; the rest is enough context to re-find the source entity without a
    join. Append-only and never edited in place.
    """

    __tablename__ = "network_audit_event"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())

    action: AuditAction = Field(sa_column=_AuditActionCol)
    actor: str = Field(default="", max_length=255, description="username")
    actor_agency_id: uuid.UUID | None = Field(default=None, index=True)

    # What it was about.
    entity_type: str = Field(default="", max_length=64, description="share|transfer|commission|...")
    entity_id: uuid.UUID | None = Field(default=None, index=True)
    property_id: uuid.UUID | None = Field(default=None, index=True)
    target_agency_id: uuid.UUID | None = Field(default=None, index=True)

    detail: str = Field(default="", max_length=2000)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
