from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.properties import PublicListingDTO, PublicMediaDTO
from app.services.publication_policy import (
    PublicationCandidate,
    PublicationDecision,
    PublicMediaCandidate,
    can_public_read,
    public_media_url_allowed,
)
from app.services.publication_lifecycle import _can_consent, _can_manage, _can_review
from app.services.public_text import sanitize_public_text
from app.core.identity import Principal
from app.models.enums import SaasTier, UserRole
from types import SimpleNamespace


NOW = datetime.now(timezone.utc)


def _candidate(**overrides):
    values = dict(
        operational_active=True,
        consent_given=True,
        consent_actor_subject="owner-test",
        consented_at=NOW,
        consent_version="terms-v1",
        review_approved=True,
        content_reviewed=True,
        publish_starts_at=NOW - timedelta(minutes=1),
        publish_ends_at=NOW + timedelta(days=1),
        revoked=False,
        media=(PublicMediaCandidate(True, True, False, True, "https://test.invalid/media.webp"),),
    )
    values.update(overrides)
    return PublicationCandidate(**values)


def test_publication_policy_allows_only_complete_valid_evidence():
    assert can_public_read(_candidate(), now=NOW) is PublicationDecision.ALLOW


def test_publication_policy_denies_missing_consent_review_expiry_or_revocation():
    for overrides in (
        {"consent_given": False},
        {"review_approved": False},
        {"content_reviewed": False},
        {"publish_ends_at": NOW - timedelta(seconds=1)},
        {"revoked": True},
    ):
        assert can_public_read(_candidate(**overrides), now=NOW) is PublicationDecision.DENY


def test_private_media_and_internal_share_do_not_become_public():
    media = PublicMediaCandidate(True, False, False, True, "https://test.invalid/media.webp")
    assert can_public_read(_candidate(media=(media,)), now=NOW) is PublicationDecision.DENY
    assert can_public_read(_candidate(media=()), now=NOW) is PublicationDecision.ALLOW


def test_public_dto_is_an_explicit_non_internal_allowlist():
    fields = set(PublicListingDTO.model_fields) | set(PublicMediaDTO.model_fields)
    forbidden = {
        "id", "owner_id", "phone_number", "exact_address", "precise_coordinates",
        "private_notes", "agency_id", "workspace_id", "local_path", "source_ref",
        "status", "review_note_private",
    }
    assert fields.isdisjoint(forbidden)
    dto = PublicListingDTO(
        public_id=uuid4(), sanitized_title="آگهی بررسی‌شده",
        sanitized_description="توضیح عمومی بررسی‌شده", property_type="APARTMENT",
        deal_type="SALE",
    )
    assert "owner_id" not in dto.model_dump()


def test_lifecycle_scope_requires_owner_or_same_workspace_and_review_role():
    agent = Principal(
        subject="agent-test", realm_roles=frozenset({"ROLE_SENIOR_BROKER"}),
        roles=frozenset({UserRole.AGENT}), kyc_status="VERIFIED", saas_tier=SaasTier.PRO,
    )
    supervisor = Principal(
        subject="supervisor-test", realm_roles=frozenset({"ROLE_SUPERVISOR"}),
        roles=frozenset({UserRole.SUPERVISOR}), kyc_status="VERIFIED", saas_tier=SaasTier.PRO,
    )
    workspace = uuid4()
    prop = SimpleNamespace(agency_id=workspace, owner_subject="other")
    assert _can_manage(prop, agent, workspace) is True
    assert _can_manage(prop, agent, uuid4()) is False
    assert _can_manage(prop, agent, None) is False
    assert _can_review(supervisor) is True
    assert _can_review(agent) is False
    prop.owner_subject = "agent-test"
    assert _can_consent(prop, agent) is True
    prop.owner_subject = "other"
    assert _can_consent(prop, agent) is False


def test_public_text_sanitizer_strips_markup_and_sensitive_values():
    result = sanitize_public_text("<script>alert(1)</script>خانه <b>خوب</b> تماس 09121234567")
    assert result is not None
    assert "script" not in result.text.lower()
    assert "09121234567" not in result.text
    assert "خانه خوب" in result.text
    assert len(result.version_hash) == 64


def test_raw_media_urls_and_unsafe_mime_are_never_public():
    assert public_media_url_allowed(mime_type="image/webp", derivative_url="https://cdn.test/1.webp")
    assert not public_media_url_allowed(mime_type="image/webp", derivative_url="file:///srv/media/1.webp")
    assert not public_media_url_allowed(mime_type="text/html", derivative_url="https://cdn.test/1.html")
