"""Professional onboarding applications (ثبت‌نام تخصصی همکاران).

A row is created when a mobile-verified user submits the professional
funnel. It records *what was requested* (``requested_role``) separately
from *what was granted* (``assigned_role``): until a manager approves,
nothing here confers access -- role mapping happens only through the
approval endpoint, which writes to Keycloak and flips ``status``.

Status vocabulary (plain strings, not a PG enum, so future states need no
migration): ``PROFILE_INCOMPLETE`` → ``ROLE_REVIEW_PENDING`` →
``ACTIVE`` | ``REJECTED``; ``SUSPENDED`` for post-approval bans.
``AGENCY_REVIEW_PENDING`` / ``IDENTITY_REVIEW_PENDING`` mark agency-track
rows waiting on office papers.

``AuthAuditLog`` next to it records security-relevant auth events
(OTP outcomes are Redis-audited by mobile; this table covers
registration decisions and token-exchange failures). It stores masked
mobiles and outcome codes only -- never OTP codes, secrets or tokens.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import timestamp_column, utcnow, uuid_column


class ProfessionalApplication(SQLModel, table=True):
    """One professional-track request, awaiting (or denied) review."""

    __tablename__ = "professional_application"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    # Canonical E.164 mobile (``+989...``); unique per open request is
    # enforced at the service layer so a duplicate submit updates in place.
    mobile: str = Field(index=True, max_length=16)
    # Keycloak user id once the account exists (nullable: the row may predate
    # provisioning when Keycloak is unreachable at submit time).
    keycloak_user_id: str = Field(default="", max_length=64)
    # Realm role the applicant asked for (must be in the allow-list).
    requested_role: str = Field(max_length=64)
    # Realm role actually granted on approval (empty until approved).
    assigned_role: str = Field(default="", max_length=64)
    first_name: str = Field(default="", max_length=128)
    last_name: str = Field(default="", max_length=128)
    email: str = Field(default="", max_length=255)
    # Free-form, track-specific payload (agency papers refs, cities, invite
    # code presence flag -- never raw secrets; validated per-track).
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = Field(default="ROLE_REVIEW_PENDING", max_length=32, index=True)
    reviewer_note: str = Field(default="", max_length=2000)
    reviewed_by: str = Field(default="", max_length=255)
    reviewed_at: datetime | None = Field(
        default=None, sa_column=timestamp_column(nullable=True)
    )
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class AuthAuditLog(SQLModel, table=True):
    """Security-relevant auth events (no secrets, ever)."""

    __tablename__ = "auth_audit_log"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    # ``otp.request`` / ``otp.verify`` / ``quick.register`` /
    # ``professional.submit`` / ``professional.approve`` /
    # ``professional.reject`` / ``token.exchange``.
    event: str = Field(max_length=64, index=True)
    masked_mobile: str = Field(default="", max_length=32)
    keycloak_user_id: str = Field(default="", max_length=64)
    outcome: str = Field(default="", max_length=32)
    detail: str = Field(default="", max_length=1000)
    client_ip: str = Field(default="", max_length=64)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


__all__ = ["AuthAuditLog", "ProfessionalApplication"]
