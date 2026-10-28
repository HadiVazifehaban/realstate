"""Internal publication lifecycle commands; no public route is registered."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.core.identity import Principal
from app.models.enums import UserRole
from app.models.property import Property
from app.models.property_media import PropertyMedia
from app.models.publication import (
    PublicationAuditEvent,
    PublicationConsentStatus,
    PublicationReviewStatus,
    PropertyMediaPublication,
    PropertyPublication,
    PropertyPublicationAudit,
)
from app.services.public_text import sanitize_public_text


class PublicationAuthorizationError(PermissionError):
    """Raised when a lifecycle command lacks property or moderation authority."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _can_manage(prop: Property, principal: Principal, workspace_id: uuid.UUID | None) -> bool:
    if "ROLE_ADMIN" in principal.realm_roles:
        return True
    if prop.agency_id is None:
        return bool(
            prop.owner_subject == principal.subject
            and principal.roles.intersection({UserRole.OWNER, UserRole.AGENT, UserRole.OFFICE_MANAGER})
        )
    return bool(
        workspace_id is not None
        and prop.agency_id == workspace_id
        and principal.roles.intersection(
            {UserRole.OWNER, UserRole.AGENT, UserRole.OFFICE_MANAGER}
        )
    )


def _can_review(principal: Principal) -> bool:
    return bool(principal.realm_roles.intersection({"ROLE_ADMIN", "ROLE_SUPERVISOR"}))


def _can_consent(prop: Property, principal: Principal) -> bool:
    """Consent requires the recorded owner; delegation is not yet modeled."""
    return prop.owner_subject == principal.subject and bool(
        principal.roles.intersection({UserRole.OWNER, UserRole.AGENT, UserRole.OFFICE_MANAGER})
    )


async def _property(session: AsyncSession, property_id: uuid.UUID) -> Property:
    prop = await session.get(Property, property_id)
    if prop is None:
        raise PublicationAuthorizationError("property_not_found")
    return prop


async def _publication(session: AsyncSession, property_id: uuid.UUID) -> PropertyPublication:
    row = (await session.exec(
        select(PropertyPublication)
        .where(PropertyPublication.property_id == property_id)
        .with_for_update()
    )).first()
    if row is None:
        row = PropertyPublication(property_id=property_id)
        session.add(row)
        await session.flush()
    return row


def _snapshot(row: PropertyPublication) -> dict:
    return {
        "consent_status": row.consent_status.value,
        "review_status": row.review_status.value,
        "publish_starts_at": row.publish_starts_at.isoformat() if row.publish_starts_at else None,
        "publish_ends_at": row.publish_ends_at.isoformat() if row.publish_ends_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
    }


async def _audit(
    session: AsyncSession,
    row: PropertyPublication,
    prop: Property,
    event: PublicationAuditEvent,
    actor_subject: str,
    before: dict,
    after: dict,
) -> None:
    session.add(PropertyPublicationAudit(
        publication_id=row.property_id,
        property_id=prop.id,
        event=event,
        actor_subject=actor_subject,
        before_json=before,
        after_json=after,
    ))


async def record_consent(
    session: AsyncSession,
    property_id: uuid.UUID,
    principal: Principal,
    workspace_id: uuid.UUID | None,
    *,
    consent_version: str,
) -> PropertyPublication:
    prop = await _property(session, property_id)
    if not _can_consent(prop, principal) or not consent_version.strip():
        raise PublicationAuthorizationError("publication_consent_denied")
    row = await _publication(session, property_id)
    before = _snapshot(row)
    row.consent_status = PublicationConsentStatus.GIVEN
    row.consent_actor_subject = principal.subject
    row.consented_at = _now()
    row.consent_version = consent_version.strip()
    row.revoked_at = None
    row.revoked_by_subject = None
    row.review_status = PublicationReviewStatus.PENDING
    await _audit(session, row, prop, PublicationAuditEvent.CONSENT_GIVEN, principal.subject, before, _snapshot(row))
    return row


async def revoke_consent(
    session: AsyncSession, property_id: uuid.UUID, principal: Principal, workspace_id: uuid.UUID | None,
    *, reason: str,
) -> PropertyPublication:
    prop = await _property(session, property_id)
    row = await _publication(session, property_id)
    if not (_can_consent(prop, principal) and (
        row.consent_actor_subject == principal.subject or "ROLE_ADMIN" in principal.realm_roles
    )):
        raise PublicationAuthorizationError("publication_revoke_denied")
    before = _snapshot(row)
    row.consent_status = PublicationConsentStatus.REVOKED
    row.revoked_at = _now()
    row.revoked_by_subject = principal.subject
    row.revocation_reason = reason.strip()[:512]
    await _audit(session, row, prop, PublicationAuditEvent.CONSENT_REVOKED, principal.subject, before, _snapshot(row))
    return row


async def submit_for_review(
    session: AsyncSession, property_id: uuid.UUID, principal: Principal, workspace_id: uuid.UUID | None,
) -> PropertyPublication:
    prop = await _property(session, property_id)
    if not _can_manage(prop, principal, workspace_id):
        raise PublicationAuthorizationError("publication_submit_denied")
    row = await _publication(session, property_id)
    if row.consent_status is not PublicationConsentStatus.GIVEN:
        raise PublicationAuthorizationError("publication_consent_required")
    before = _snapshot(row)
    row.review_status = PublicationReviewStatus.PENDING
    await _audit(session, row, prop, PublicationAuditEvent.SUBMITTED, principal.subject, before, _snapshot(row))
    return row


async def set_sanitized_content(
    session: AsyncSession,
    property_id: uuid.UUID,
    principal: Principal,
    workspace_id: uuid.UUID | None,
    *,
    title: str,
    description: str,
) -> PropertyPublication:
    """Store sanitized copy and invalidate any previous moderation decision."""
    prop = await _property(session, property_id)
    if not _can_consent(prop, principal):
        raise PublicationAuthorizationError("publication_content_denied")
    clean_title = sanitize_public_text(title, max_length=255)
    clean_description = sanitize_public_text(description, max_length=2000)
    if clean_title is None or clean_description is None:
        raise PublicationAuthorizationError("publication_content_empty")
    row = await _publication(session, property_id)
    before = _snapshot(row)
    row.sanitized_title = clean_title.text
    row.sanitized_description = clean_description.text
    row.content_reviewed_at = None
    row.content_reviewed_by_subject = None
    row.review_status = PublicationReviewStatus.PENDING
    await _audit(
        session, row, prop, PublicationAuditEvent.SUBMITTED, principal.subject, before,
        {**_snapshot(row), "content_hash": clean_title.version_hash + clean_description.version_hash},
    )
    return row


async def review_publication(
    session: AsyncSession, property_id: uuid.UUID, principal: Principal, *, approved: bool, note: str | None = None,
) -> PropertyPublication:
    if not _can_review(principal):
        raise PublicationAuthorizationError("publication_review_denied")
    prop = await _property(session, property_id)
    row = (await session.exec(
        select(PropertyPublication)
        .where(PropertyPublication.property_id == property_id)
        .with_for_update()
    )).first()
    if row is None or row.consent_status is not PublicationConsentStatus.GIVEN:
        raise PublicationAuthorizationError("publication_consent_required")
    if approved and (not row.sanitized_title or not row.sanitized_description):
        raise PublicationAuthorizationError("publication_sanitized_content_required")
    if row.consent_actor_subject == principal.subject:
        raise PublicationAuthorizationError("publication_separation_of_duties")
    before = _snapshot(row)
    row.review_status = PublicationReviewStatus.APPROVED if approved else PublicationReviewStatus.REJECTED
    row.reviewed_by_subject = principal.subject
    row.reviewed_at = _now()
    row.review_note_private = note
    row.content_reviewed_at = _now() if approved else None
    row.content_reviewed_by_subject = principal.subject if approved else None
    event = PublicationAuditEvent.APPROVED if approved else PublicationAuditEvent.REJECTED
    await _audit(session, row, prop, event, principal.subject, before, _snapshot(row))
    return row


async def approve_media(
    session: AsyncSession,
    property_id: uuid.UUID,
    media_id: uuid.UUID,
    principal: Principal,
    *,
    approved: bool,
) -> PropertyMediaPublication:
    if not _can_review(principal):
        raise PublicationAuthorizationError("media_review_denied")
    prop = await _property(session, property_id)
    media = await session.get(PropertyMedia, media_id)
    if media is None or media.property_id != property_id:
        raise PublicationAuthorizationError("media_not_found")
    publication = (await session.exec(
        select(PropertyPublication)
        .where(PropertyPublication.property_id == property_id)
        .with_for_update()
    )).first()
    if publication is None or publication.consent_status is not PublicationConsentStatus.GIVEN:
        raise PublicationAuthorizationError("publication_consent_required")
    if publication.consent_actor_subject == principal.subject:
        raise PublicationAuthorizationError("publication_separation_of_duties")
    row = await session.get(PropertyMediaPublication, (property_id, media_id))
    if row is None:
        row = PropertyMediaPublication(property_id=property_id, media_id=media_id)
        session.add(row)
    row.allow_public = approved
    row.review_status = PublicationReviewStatus.APPROVED if approved else PublicationReviewStatus.REJECTED
    row.reviewed_by_subject = principal.subject
    row.reviewed_at = _now()
    await _audit(
        session, publication, prop,
        PublicationAuditEvent.MEDIA_APPROVED if approved else PublicationAuditEvent.MEDIA_REJECTED,
        principal.subject, {}, {"media_id": str(media_id), "allow_public": approved},
    )
    return row


async def schedule_publication(
    session: AsyncSession, property_id: uuid.UUID, principal: Principal, workspace_id: uuid.UUID | None,
    *, starts_at: datetime, ends_at: datetime,
) -> PropertyPublication:
    prop = await _property(session, property_id)
    if not _can_consent(prop, principal):
        raise PublicationAuthorizationError("publication_schedule_denied")
    row = await _publication(session, property_id)
    if row.consent_status is not PublicationConsentStatus.GIVEN or row.review_status is not PublicationReviewStatus.APPROVED:
        raise PublicationAuthorizationError("publication_review_required")
    if ends_at <= starts_at:
        raise PublicationAuthorizationError("publication_window_invalid")
    before = _snapshot(row)
    row.publish_starts_at = starts_at
    row.publish_ends_at = ends_at
    row.revoked_at = None
    await _audit(session, row, prop, PublicationAuditEvent.SCHEDULED, principal.subject, before, _snapshot(row))
    return row


async def unpublish(
    session: AsyncSession, property_id: uuid.UUID, principal: Principal, workspace_id: uuid.UUID | None,
    *, reason: str,
) -> PropertyPublication:
    prop = await _property(session, property_id)
    if not (_can_manage(prop, principal, workspace_id) or _can_review(principal)):
        raise PublicationAuthorizationError("publication_unpublish_denied")
    row = await _publication(session, property_id)
    before = _snapshot(row)
    row.revoked_at = _now()
    row.revoked_by_subject = principal.subject
    row.revocation_reason = reason.strip()[:512]
    await _audit(session, row, prop, PublicationAuditEvent.UNPUBLISHED, principal.subject, before, _snapshot(row))
    return row
