"""Fail-closed publication decision logic.

This module is deliberately storage- and router-independent. Gate 1.7 only
defines the policy; no public route or database publication model is wired yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class PublicationDecision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"


SAFE_PUBLIC_MIME_TYPES = frozenset({"image/avif", "image/webp", "image/jpeg", "image/png"})


def public_media_url_allowed(*, mime_type: str, derivative_url: str | None) -> bool:
    """Only a generated derivative can ever be eligible for public delivery."""
    return bool(
        mime_type.lower() in SAFE_PUBLIC_MIME_TYPES
        and derivative_url
        and derivative_url.startswith("https://")
        and not derivative_url.startswith("https://localhost")
    )


@dataclass(frozen=True)
class PublicMediaCandidate:
    allow_public: bool
    approved: bool
    revoked: bool
    safe_mime: bool
    derivative_url: str | None


@dataclass(frozen=True)
class PublicationCandidate:
    operational_active: bool
    consent_given: bool
    consent_actor_subject: str | None
    consented_at: datetime | None
    consent_version: str | None
    review_approved: bool
    content_reviewed: bool
    publish_starts_at: datetime | None
    publish_ends_at: datetime | None
    revoked: bool
    media: tuple[PublicMediaCandidate, ...]


def can_public_read(candidate: PublicationCandidate, *, now: datetime) -> PublicationDecision:
    """Evaluate every publication predicate; any missing proof denies access."""
    if not candidate.operational_active:
        return PublicationDecision.DENY
    if not (
        candidate.consent_given
        and candidate.consent_actor_subject
        and candidate.consented_at
        and candidate.consent_version
    ):
        return PublicationDecision.DENY
    if not candidate.review_approved or not candidate.content_reviewed:
        return PublicationDecision.DENY
    if (
        candidate.publish_starts_at is None
        or candidate.publish_ends_at is None
        or candidate.publish_ends_at <= candidate.publish_starts_at
        or now < candidate.publish_starts_at
        or now >= candidate.publish_ends_at
    ):
        return PublicationDecision.DENY
    if candidate.revoked:
        return PublicationDecision.DENY
    if any(
        not media.allow_public
        or not media.approved
        or media.revoked
        or not media.safe_mime
        or not media.derivative_url
        for media in candidate.media
    ):
        return PublicationDecision.DENY
    return PublicationDecision.ALLOW
