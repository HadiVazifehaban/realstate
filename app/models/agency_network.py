"""Inter-agency collaboration network (شبکه همکاری دفاتر).

The node began as a single-office install -- ``AgencyUser.agency_id`` defaulted
to ``"local"`` and there was nowhere for a second office to live. This module is
the seed of the MLS network: offices exist as first-class rows, and a
*cooperation agreement* is what lets two of them work a file together.

Three distinctions drive the whole model and are worth stating because getting
them wrong is what makes network features unauditable:

* an **office** is a party, a **membership** is a person in it, a **cooperation**
  is a relationship *between* two offices. None of the three implies either of
  the others.
* a **cooperation** is the permission to work together; a **share** (later
  phase) is access to one file. Revoking a share must not end the relationship,
  and ending the relationship must not silently keep the share alive.
* a cooperation's history is append-only. Re-approving after a rejection is a
  new row, so "when did these offices stop trusting each other, and why" stays
  answerable.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Column, Field, SQLModel

from app.models.base import pg_enum, timestamp_column, utcnow, uuid_column
from app.models.enums import (
    AgencyStatus,
    CooperationScope,
    CooperationStatus,
)

_StatusCol = Column(pg_enum(AgencyStatus, "agency_status"), nullable=False, default=AgencyStatus.PENDING)
_CoopStatusCol = Column(pg_enum(CooperationStatus, "cooperation_status"), nullable=False, default=CooperationStatus.PENDING)
_ScopeCol = Column(pg_enum(CooperationScope, "cooperation_scope"), nullable=False, default=CooperationScope.SHARE_LISTINGS)


class Agency(SQLModel, table=True):
    """A real-estate office on the collaboration network."""

    __tablename__ = "agency"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    # The stable handle other nodes address this office by. Not a display name:
    # offices rename, and a rename must not break every agreement pointing here.
    slug: str = Field(index=True, unique=True, max_length=64)
    name: str = Field(max_length=255)
    name_fa: str = Field(default="", max_length=255, description="نمایش فارسی")
    city: str = Field(default="", max_length=64)
    district: str = Field(default="", max_length=64)
    phone: str = Field(default="", max_length=32)
    logo_url: str = Field(default="", max_length=512)
    description: str = Field(default="", max_length=2000)

    status: AgencyStatus = Field(
        default=AgencyStatus.PENDING, sa_column=_StatusCol
    )

    # Who on the network vouched for this office. Blank for the node's own
    # office, which bootstraps itself and cannot be vouched for by anybody.
    verified_by: str = Field(default="", max_length=255)

    # Settlement identity, so a commission ledger has somewhere to point. Kept
    # as free text until real banking integration is justified.
    settlement_iban: str = Field(default="", max_length=34)

    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())

    @property
    def display_name(self) -> str:
        """The Persian name when we have one, else the slug."""
        return self.name_fa or self.name or self.slug


class AgencyCooperation(SQLModel, table=True):
    """A request for, or grant of, the right to work with another office.

    One row per request, and a re-request after a rejection is a *new* row --
    the history of "these two offices agreed, then fell out, then agreed again"
    is the thing a dispute will ask about, so overwriting it in place is not an
    option.
    """

    __tablename__ = "agency_cooperation"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())

    # Both sides. Deliberately not a single "other office" column: an outgoing
    # and an incoming request are the same relationship seen from either end,
    # and queries on "who asked whom" must not depend on which node you sit on.
    requester_agency_id: uuid.UUID = Field(index=True, description="دفتر درخواست‌کننده")
    target_agency_id: uuid.UUID = Field(index=True, description="دفتر هدف")

    status: CooperationStatus = Field(
        default=CooperationStatus.PENDING, sa_column=_CoopStatusCol
    )
    # The shape of work the two offices asked for. A relationship can carry more
    # than one scope, so this is the *requested* scope; the granted one lives in
    # ``granted_scopes`` once somebody approves.
    scope: CooperationScope = Field(
        default=CooperationScope.SHARE_LISTINGS, sa_column=_ScopeCol
    )
    granted_scopes: str = Field(
        default="",
        max_length=255,
        description="Comma-separated granted scopes; empty means 'as requested'",
    )

    # Default commission split proposed for this relationship, in percent.
    # The per-deal split can override it; this is what an advisor sees when they
    # are deciding whether to open a co-broke file at all.
    default_commission_pct: int = Field(default=50, ge=0, le=100)

    expires_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    decided_at: datetime | None = Field(
        default=None, sa_column=timestamp_column(nullable=True)
    )
    # Required when rejecting: "no thanks" with no reason is the single most
    # common cause of a network admin having to phone the other office.
    decision_reason: str = Field(default="", max_length=1000)

    requested_by: str = Field(default="", max_length=255, description="username")
    decided_by: str = Field(default="", max_length=255, description="username")

    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())

    @property
    def granted_scope_list(self) -> list[CooperationScope]:
        """The scopes this relationship actually carries.

        Falls back to the requested scope so a freshly approved row behaves the
        same as one an admin trimmed by hand.
        """
        raw = self.granted_scopes.strip()
        if not raw:
            return [self.scope]
        out: list[CooperationScope] = []
        for item in raw.split(","):
            item = item.strip()
            if not item:
                continue
            try:
                out.append(CooperationScope(item))
            except ValueError:
                # An unknown scope in the column is data drift, not a reason to
                # refuse every listing on the network.
                continue
        return out or [self.scope]
