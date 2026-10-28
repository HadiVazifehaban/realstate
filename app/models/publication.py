"""Database model proposal for the dark-mode public publication contract."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column, ForeignKeyConstraint, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.base import pg_enum, timestamp_column, utcnow, uuid_column


class PublicationConsentStatus(StrEnum):
    NOT_GIVEN = "NOT_GIVEN"
    GIVEN = "GIVEN"
    REVOKED = "REVOKED"


class PublicationReviewStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PublicationAuditEvent(StrEnum):
    CONSENT_GIVEN = "CONSENT_GIVEN"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MEDIA_APPROVED = "MEDIA_APPROVED"
    MEDIA_REJECTED = "MEDIA_REJECTED"
    SCHEDULED = "SCHEDULED"
    UNPUBLISHED = "UNPUBLISHED"
    EXPIRED = "EXPIRED"


class PropertyPublication(SQLModel, table=True):
    __tablename__ = "property_publication"

    property_id: uuid.UUID = Field(foreign_key="property.id", primary_key=True)
    public_id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    consent_status: PublicationConsentStatus = Field(
        default=PublicationConsentStatus.NOT_GIVEN,
        sa_column=Column(pg_enum(PublicationConsentStatus, "publication_consent_status"), nullable=False),
    )
    consent_actor_subject: str | None = Field(default=None, max_length=255)
    consented_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    consent_version: str | None = Field(default=None, max_length=128)
    review_status: PublicationReviewStatus = Field(
        default=PublicationReviewStatus.PENDING,
        sa_column=Column(pg_enum(PublicationReviewStatus, "publication_review_status"), nullable=False),
    )
    reviewed_by_subject: str | None = Field(default=None, max_length=255)
    reviewed_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    review_note_private: str | None = Field(default=None)
    publish_starts_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    publish_ends_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    revoked_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    revoked_by_subject: str | None = Field(default=None, max_length=255)
    revocation_reason: str | None = Field(default=None, max_length=512)
    sanitized_title: str | None = Field(default=None)
    sanitized_description: str | None = Field(default=None)
    content_reviewed_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    content_reviewed_by_subject: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class PropertyMediaPublication(SQLModel, table=True):
    __tablename__ = "property_media_publication"
    __table_args__ = (
        ForeignKeyConstraint(
            ["property_id", "media_id"],
            ["property_media.property_id", "property_media.id"],
            name="fk_media_publication_property_media",
            ondelete="CASCADE",
        ),
        UniqueConstraint("property_id", "media_id", name="uq_property_media_publication_pair"),
    )

    property_id: uuid.UUID = Field(primary_key=True)
    media_id: uuid.UUID = Field(primary_key=True)
    allow_public: bool = Field(default=False, nullable=False)
    review_status: PublicationReviewStatus = Field(
        default=PublicationReviewStatus.PENDING,
        sa_column=Column(pg_enum(PublicationReviewStatus, "media_publication_review_status"), nullable=False),
    )
    reviewed_by_subject: str | None = Field(default=None, max_length=255)
    reviewed_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    revoked_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class PropertyPublicationAudit(SQLModel, table=True):
    __tablename__ = "property_publication_audit"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    publication_id: uuid.UUID = Field(foreign_key="property_publication.property_id", index=True)
    media_publication_id: uuid.UUID | None = Field(default=None, index=True)
    property_id: uuid.UUID = Field(index=True)
    event: PublicationAuditEvent = Field(
        sa_column=Column(pg_enum(PublicationAuditEvent, "publication_audit_event"), nullable=False)
    )
    actor_subject: str = Field(max_length=255)
    correlation_id: str | None = Field(default=None, max_length=128)
    before_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    after_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
