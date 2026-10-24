"""Phase 5 tests: pipeline transitions, timeline and the quota-gated PII vault.

These assert the rules that carry real risk:
* a card cannot skip a column, and only ADMIN may reopen a closed deal;
* a visit lives on the timeline as a ``VISIT_EVENT``, never on a property;
* a phone number is never returned without role + quota + an audit row.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.core.crypto import PiiCipher
from app.models import CrmLead, OwnerAccessLog, Property
from app.models.enums import (
    KANBAN_COLUMNS,
    LEAD_TRANSITIONS,
    DATA_GOVERNOR_ROLES,
    PII_READER_ROLES,
    DealType,
    LeadPriority,
    LeadStage,
    PropertySource,
    SaasTier,
    UserRole,
    ValuationStatus,
)
from app.services import crm as crm_service
from app.services import pii_vault
from app.services.ingestion.deduplicator import (
    AUTO_MERGE_CONFIDENCE,
    QUARANTINE_CONFIDENCE,
    precedence_for,
    score_candidate,
)


# --------------------------------------------------------------------------- #
# Pipeline rules
# --------------------------------------------------------------------------- #
def test_five_kanban_columns_are_declared() -> None:
    assert len(KANBAN_COLUMNS) == 5
    assert LeadStage.LOST_ARCHIVED not in KANBAN_COLUMNS


def test_a_card_cannot_skip_a_column() -> None:
    with pytest.raises(crm_service.InvalidTransition):
        crm_service.assert_transition_allowed(
            LeadStage.NEW_FILE, LeadStage.CLOSED_DEAL, role=UserRole.ADMIN
        )
    assert LeadStage.CONTRACT_READY not in LEAD_TRANSITIONS[LeadStage.CONTACTING]


def test_reopening_a_closed_deal_needs_admin() -> None:
    with pytest.raises(crm_service.TransitionNotPermitted):
        crm_service.assert_transition_allowed(
            LeadStage.CLOSED_DEAL, LeadStage.APPRAISAL, role=UserRole.AGENT
        )
    crm_service.assert_transition_allowed(
        LeadStage.CLOSED_DEAL, LeadStage.APPRAISAL, role=UserRole.ADMIN
    )


def test_every_forward_step_is_reachable() -> None:
    """No column may be a dead end — otherwise a deal gets stuck on the board."""
    for column in KANBAN_COLUMNS[:-1]:
        assert LEAD_TRANSITIONS[column], column


def test_bargain_outranks_normal_priority() -> None:
    assert (
        crm_service.priority_for(ValuationStatus.BARGAIN, -20.0)
        is LeadPriority.URGENT_BARGAIN
    )
    assert crm_service.priority_for(ValuationStatus.FAIR, 0.0) is LeadPriority.NORMAL


async def test_a_visit_must_carry_an_appointment_time() -> None:
    """A visit without a time is a data error, not a free-text note."""
    lead = CrmLead(property_id=uuid.uuid4())

    class _Session:
        def add(self, obj: object) -> None:
            return None

        async def flush(self) -> None:
            return None

    from app.models.enums import InteractionType

    with pytest.raises(ValueError):
        await crm_service.log_interaction(
            _Session(),  # type: ignore[arg-type]
            lead,
            interaction_type=InteractionType.VISIT_EVENT,
            scheduled_at=None,
        )


# --------------------------------------------------------------------------- #
# PII vault
# --------------------------------------------------------------------------- #
def test_mask_keeps_the_number_unrecoverable() -> None:
    masked = pii_vault.mask_phone("09123456789")
    assert masked == "0912***6789"
    # The middle digits — the identifying part — are gone.
    assert "3456" not in (masked or "")


def test_quota_matches_the_published_plan() -> None:
    assert pii_vault.quota_for(SaasTier.FREE) == 5
    assert pii_vault.quota_for(SaasTier.BASIC) == 30
    assert pii_vault.quota_for(SaasTier.PRO) == 100
    assert pii_vault.quota_for(SaasTier.ENTERPRISE) == -1  # unlimited


def test_only_desk_roles_may_read_the_vault() -> None:
    assert UserRole.GUEST not in PII_READER_ROLES
    assert UserRole.OWNER not in PII_READER_ROLES
    assert UserRole.AGENT in PII_READER_ROLES
    assert UserRole.ADMIN in PII_READER_ROLES


async def test_a_denied_reveal_is_still_audited() -> None:
    """Brute-forcing the endpoint must be visible to a supervisor."""

    class _Session:
        def __init__(self) -> None:
            self.added: list[object] = []

        def add(self, obj: object) -> None:
            self.added.append(obj)

        async def flush(self) -> None:
            return None

    session = _Session()
    with pytest.raises(pii_vault.PiiAccessDenied) as exc:
        await pii_vault.reveal_owner_phone(
            session,  # type: ignore[arg-type]
            property_id=uuid.uuid4(),
            actor_user_id=uuid.uuid4(),
            role=UserRole.GUEST,
            tier=SaasTier.ENTERPRISE,
            cipher=PiiCipher(PiiCipher.generate_key()),
        )

    assert exc.value.reason == "role_not_permitted"
    logs = [obj for obj in session.added if isinstance(obj, OwnerAccessLog)]
    assert logs and all(entry.allowed is False for entry in logs)


# --------------------------------------------------------------------------- #
# Provenance precedence (Phase 4)
# --------------------------------------------------------------------------- #
def test_owner_registration_outranks_a_scrape() -> None:
    assert (
        precedence_for(PropertySource.INTERNAL_USER)
        > precedence_for(PropertySource.INTERNAL_AGENCY)
    )
    assert (
        precedence_for(PropertySource.INTERNAL_AGENCY)
        > precedence_for(PropertySource.DIVAR)
    )
    # Portals carry equal weight: neither is more trustworthy than the other.
    assert precedence_for(PropertySource.DIVAR) == precedence_for(
        PropertySource.SHEYPOOR
    )


def test_legacy_sources_keep_their_rank() -> None:
    """A pre-migration row must not lose a merge for no principled reason."""
    assert precedence_for(PropertySource.MANUAL_OFFICE) == precedence_for(
        PropertySource.INTERNAL_AGENCY
    )
    assert precedence_for(PropertySource.DIVAR_KENAR) == precedence_for(
        PropertySource.DIVAR
    )


def _prop(lat: float, lng: float, **overrides: object) -> Property:
    # Defaults first, then the caller's overrides, so a test can vary any spec.
    specs: dict[str, object] = {"area": 100.0, "rooms": 2, "floor": 3}
    specs.update(overrides)
    return Property(latitude=lat, longitude=lng, **specs)  # type: ignore[arg-type]


def test_same_unit_nearby_scores_above_auto_merge() -> None:
    """~11 m apart with identical specs is the same flat."""
    match = score_candidate(
        _prop(35.79512, 51.43120),
        _prop(35.79522, 51.43120),
        phone_blind_index="abc",
        candidate_phone_blind_index="abc",
    )
    assert match is not None
    assert match.confidence >= AUTO_MERGE_CONFIDENCE


def test_far_apart_is_rejected_outright() -> None:
    # ~530 m: different buildings, so no score is returned at all.
    assert (
        score_candidate(_prop(35.79512, 51.43120), _prop(35.80000, 51.43120))
        is None
    )


def test_different_deal_type_is_never_a_duplicate() -> None:
    assert (
        score_candidate(
            _prop(35.79512, 51.43120),
            _prop(35.79513, 51.43120, deal_type=DealType.RENT),
        )
        is None
    )


def test_ambiguous_pair_lands_in_the_quarantine_band() -> None:
    """Plausible but unprovable: queued for review instead of merged blindly.

    Same building, identical area and beds, ~5 m apart, but one ad omitted the
    floor. That is exactly the case a human should decide: merging on it risks
    collapsing two different flats on one storey.
    """
    match = score_candidate(
        _prop(35.79512, 51.43120, floor=3),
        _prop(35.79517, 51.43120, floor=None),
    )
    assert match is not None
    assert QUARANTINE_CONFIDENCE <= match.confidence < AUTO_MERGE_CONFIDENCE
    # The evidence is surfaced so a supervisor can see what drove the score.
    assert match.reasons["geo"] > 0.8
    assert match.reasons["beds"] == 1.0
    assert match.reasons["floor"] == 0.5  # "unknown", not "mismatch"


# --------------------------------------------------------------------------- #
# Lead deletion guards
# --------------------------------------------------------------------------- #
def test_delete_is_governor_only() -> None:
    """A permanent purge is a data-governor action, like merging duplicates.

    An agent removing their own mistake is the real case, and the reversible
    LOST_ARCHIVED path covers it -- so the hard delete stays restricted.
    """
    from app.api.v1.endpoints.crm import delete_lead_route  # noqa: F401

    for role in (UserRole.AGENT, UserRole.OFFICE_MANAGER):
        assert role not in DATA_GOVERNOR_ROLES

    assert {UserRole.SUPERVISOR, UserRole.ADMIN} <= DATA_GOVERNOR_ROLES


def test_delete_request_demands_explicit_confirmation() -> None:
    """A body-less request must not be able to purge deal history.

    This is the guard against a stray DELETE from a misconfigured client or a
    crawler: without ``confirm`` the endpoint rejects before touching the row.
    """
    from app.schemas.crm import LeadDeleteRequest

    assert LeadDeleteRequest(confirm=True).confirm is True

    with pytest.raises(ValidationError):
        LeadDeleteRequest()  # type: ignore[call-arg]


def test_lost_archived_is_the_reversible_removal_path() -> None:
    """Archiving must be reachable from every stage, so the soft delete is
    always available -- otherwise brokers would purge to get a card off the
    board."""
    for stage in KANBAN_COLUMNS:
        if stage is LeadStage.CLOSED_DEAL:
            # A won deal is not "lost": the only way out is a governor
            # reopening it for a genuine re-trade.
            assert LeadStage.LOST_ARCHIVED not in LEAD_TRANSITIONS[stage]
            continue
        assert LeadStage.LOST_ARCHIVED in LEAD_TRANSITIONS[stage]
