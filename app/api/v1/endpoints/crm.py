"""Phase 5 CRM endpoints: the five-column board, stage moves and the timeline.

Every route is licence-gated like the rest of the paid surface. Role/tier
resolution currently reads the ``X-User-Role`` / ``X-SaaS-Tier`` headers because
node authentication is still the licence guard; ``_actor_context`` is the single
seam to swap in real session data once OIDC/Clerk lands.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlmodel import select

from app.api.deps import ActiveAgencyDep, LicenseGuard, Principal, PrincipalDep, SessionDep, SettingsDep
from app.core.crypto import PiiCipher
from app.core.identity import BOOTSTRAP_SUBJECT, ROLE_ORDER
from app.models import CrmLead, LeadInteraction, OwnerAccessLog, Property
from app.models.agency_network import Agency, AgencyMembership
from app.models.network_collab import ListingShare, ListingSharePermission
from app.models.enums import (
    DATA_GOVERNOR_ROLES,
    LeadStage,
    ListingShareMode,
    ShareStatus,
    SaasTier,
    UserRole,
)
from app.schemas.crm import (
    BoardStatsResponse,
    InteractionRequest,
    InteractionResponse,
    LeadCreateRequest,
    LeadCreateResponse,
    LeadDeleteRequest,
    LeadDeleteResponse,
    LeadDetailResponse,
    LeadListResponse,
    LeadSummary,
    PiiAccessLogEntry,
    PiiRevealRequest,
    PiiRevealResponse,
    QuotaStatusResponse,
    StageChangeRequest,
    StageStat,
)
from app.services import crm as crm_service
from app.services import pii_vault

router = APIRouter()

def _actor_context(principal: PrincipalDep) -> tuple[UserRole, SaasTier]:
    """Role and tier for the verified caller.

    In ``KEYCLOAK`` mode both come from a signed token via
    :class:`Principal` — never from a client-supplied header, which would be an
    unverifiable grant.
    """
    role = (
        max(principal.roles, key=lambda r: ROLE_ORDER[r])
        if principal.roles
        else UserRole.GUEST
    )
    return role, principal.saas_tier


def _workspace_actor_context(principal: Principal, membership: AgencyMembership) -> tuple[UserRole, str]:
    """Intersect the signed Realm role with this office's active membership."""
    realm_roles = principal.realm_roles
    member_role = membership.role.upper()
    if "ROLE_ADMIN" in realm_roles:
        return UserRole.ADMIN, "admin"
    if "ROLE_SUPERVISOR" in realm_roles and member_role in {
        "FOUNDER", "ADMIN", "OFFICE_MANAGER", "SUPERVISOR", "LEGACY_OFFICE_OPERATOR"
    }:
        return UserRole.SUPERVISOR, "supervisor"
    if "ROLE_AGENCY_MANAGER" in realm_roles and member_role in {
        "FOUNDER", "ADMIN", "OFFICE_MANAGER", "LEGACY_OFFICE_OPERATOR"
    }:
        return UserRole.OFFICE_MANAGER, "manager"
    if "ROLE_SENIOR_BROKER" in realm_roles and member_role in {"SENIOR_BROKER", "ROLE_SENIOR_BROKER", "LEGACY_SENIOR_BROKER"}:
        return UserRole.AGENT, "senior"
    if "ROLE_JUNIOR_BROKER" in realm_roles and member_role in {"JUNIOR_BROKER", "ROLE_JUNIOR_BROKER", "LEGACY_JUNIOR_BROKER"}:
        return UserRole.AGENT, "junior"
    raise HTTPException(status_code=403, detail={"error": "workspace_role_mismatch"})


async def _resolve_actor_user(session: SessionDep, principal: Principal) -> uuid.UUID:
    """Return a real ``agency_user`` id to attribute this request to.

    ``owner_access_log`` and ``pii_quota`` both carry a foreign key to
    ``agency_user``, so an audit entry pointing at nobody would be worthless.
    Keycloak subjects are projected onto a local row by username; a fresh
    install gets a node-operator row rather than failing the request.
    """
    from app.models import AgencyUser

    if principal.subject == BOOTSTRAP_SUBJECT:
        existing = (await session.exec(select(AgencyUser).limit(1))).first()
        if existing is not None:
            return existing.id
        created = AgencyUser(
            username="node-operator",
            full_name=principal.full_name or "اپراتور نود",
            role=UserRole.ADMIN,
        )
        session.add(created)
        await session.flush()
        return created.id

    # Keycloak owns the credential; the local row exists purely so quota and
    # audit rows have a real owner to point at.
    username = principal.username or principal.subject
    row = (
        await session.exec(select(AgencyUser).where(AgencyUser.username == username))
    ).first()
    if row is not None:
        return row.id

    created = AgencyUser(
        username=username[:64],
        full_name=principal.full_name[:255],
        role=(
            max(principal.roles, key=lambda r: ROLE_ORDER[r])
            if principal.roles
            else UserRole.GUEST
        ),
    )
    session.add(created)
    await session.flush()
    return created.id


async def _load_lead(session: SessionDep, lead_id: uuid.UUID, agency_id: str) -> CrmLead:
    lead = (await session.exec(select(CrmLead).where(
        CrmLead.id == lead_id, CrmLead.agency_id == agency_id
    ))).first()
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "lead_not_found"},
        )
    return lead


def _require_lead_assignment(
    lead: CrmLead, *, principal: Principal, membership_role: str,
    actor_user_id: uuid.UUID, require_senior_assignment: bool = False,
) -> None:
    assignment_required = membership_role == "junior" or (
        require_senior_assignment and membership_role == "senior"
    )
    if not assignment_required:
        return
    if lead.assigned_subject == principal.subject or lead.assigned_user_id == actor_user_id:
        return
    # Deliberately hide whether another broker's card exists in this workspace.
    raise HTTPException(status_code=404, detail={"error": "lead_not_found"})


async def _property_share_permission(
    session: SessionDep,
    prop: Property,
    *,
    agency: Agency,
    principal: Principal,
    permission_name: str,
) -> bool:
    if prop.agency_id is None or prop.agency_id == agency.id:
        return True
    now = datetime.now(timezone.utc)
    shares = (await session.exec(select(ListingShare).where(
        ListingShare.property_id == prop.id,
        ListingShare.source_agency_id == prop.agency_id,
        ListingShare.target_agency_id == agency.id,
        ListingShare.status == ShareStatus.ACTIVE,
        ListingShare.revoked_at.is_(None),
        (ListingShare.expires_at.is_(None)) | (ListingShare.expires_at > now),
        ListingShare.mode.in_([ListingShareMode.SHARE, ListingShareMode.TRANSFER]),
    ))).all()
    for share in shares:
        if share.target_agent and share.target_agent not in {principal.username, principal.subject}:
            continue
        permission = await session.get(ListingSharePermission, share.id)
        if permission is not None and bool(getattr(permission, permission_name, False)):
            return True
    return False


async def _visible_crm_property_ids(
    session: SessionDep, *, agency: Agency, principal: Principal,
) -> set[uuid.UUID]:
    property_ids = (await session.exec(select(CrmLead.property_id).where(
        CrmLead.agency_id == str(agency.id)
    ).distinct())).all()
    visible: set[uuid.UUID] = set()
    for property_id in property_ids:
        prop = await session.get(Property, property_id)
        if prop is not None and await _property_share_permission(
            session, prop, agency=agency, principal=principal, permission_name="view_summary"
        ):
            visible.add(property_id)
    return visible


async def _resolve_lead_assignee(
    session: SessionDep,
    *,
    payload: LeadCreateRequest,
    principal: Principal,
    agency: Agency,
    membership_role: str,
    actor_user_id: uuid.UUID,
) -> tuple[uuid.UUID | None, str]:
    target_subject = (payload.assigned_user_subject or "").strip()
    local_assigned_id: uuid.UUID | None = None
    active_subjects = set((await session.exec(select(AgencyMembership.user_subject).where(
        AgencyMembership.agency_id == agency.id,
        AgencyMembership.revoked_at.is_(None),
    ))).all())

    if payload.assigned_user_id is not None and not target_subject:
        target_subject = str(payload.assigned_user_id)
        if target_subject not in active_subjects:
            from app.models.agency_user import AgencyUser
            local_user = await session.get(AgencyUser, payload.assigned_user_id)
            if local_user is None or local_user.agency_id != str(agency.id):
                raise HTTPException(status_code=404, detail={"error": "assignee_not_in_workspace"})
            local_assigned_id = local_user.id
            target_subject = ""

    if not target_subject and local_assigned_id is None:
        target_subject = principal.subject
        local_assigned_id = actor_user_id
    elif target_subject:
        if target_subject not in active_subjects:
            raise HTTPException(status_code=404, detail={"error": "assignee_not_in_workspace"})
        if target_subject == principal.subject:
            local_assigned_id = actor_user_id

    if membership_role == "junior" and target_subject != principal.subject and local_assigned_id != actor_user_id:
        raise HTTPException(status_code=403, detail={"error": "junior_cannot_assign_other_member"})
    return local_assigned_id, target_subject


def _to_summary(view: crm_service.LeadView) -> LeadSummary:
    return LeadSummary(
        id=view.id,
        property_id=view.property_id,
        agency_id=view.agency_id,
        stage=view.stage,
        priority=view.priority,
        assigned_user_id=view.assigned_user_id,
        assigned_subject=view.assigned_subject,
        is_bargain=view.is_bargain,
        deviation_pct=view.deviation_pct,
        neighborhood=view.neighborhood,
        city=view.city,
        title=view.title,
        total_price=view.total_price,
        area=view.area,
        rooms=view.rooms,
        updated_at=view.updated_at,
        source=view.source,
    )


async def _timeline(session: SessionDep, lead_id: uuid.UUID) -> list[InteractionResponse]:
    events = (
        await session.exec(
            select(LeadInteraction)
            .where(LeadInteraction.lead_id == lead_id)
            .order_by(LeadInteraction.created_at.desc())  # type: ignore[arg-type]
            .limit(100)
        )
    ).all()
    return [
        InteractionResponse(
            id=event.id,
            interaction_type=event.interaction_type,
            scheduled_at=event.scheduled_at,
            note=event.note,
            created_at=event.created_at,
        )
        for event in events
    ]


@router.get(
    "/leads",
    response_model=LeadListResponse,
    summary="Board feed, optionally filtered by stage / bargain - فیلتر",
)
async def list_leads_route(
    session: SessionDep,
    _license: LicenseGuard,
    # Every desk surface is behind the identity gate: the board leaks deal flow
    # and pricing, so it must never be readable anonymously in either auth mode.
    workspace: ActiveAgencyDep,
    stage: list[LeadStage] | None = Query(default=None),
    bargains_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
) -> LeadListResponse:
    principal, membership, agency = workspace
    _role, seniority = _workspace_actor_context(principal, membership)
    actor_user_id = await _resolve_actor_user(session, principal) if seniority == "junior" else None
    global_admin = membership.role.upper() == "GLOBAL_ADMIN"
    visible_property_ids = None if global_admin else await _visible_crm_property_ids(session, agency=agency, principal=principal)
    views = await crm_service.list_leads(
        session, stages=stage, bargains_only=bargains_only, limit=limit,
        agency_id=None if global_admin else str(agency.id), property_ids=visible_property_ids,
        assigned_user_id=actor_user_id,
        assigned_subject=principal.subject if seniority == "junior" else None,
    )
    return LeadListResponse(count=len(views), items=[_to_summary(v) for v in views])


@router.get(
    "/board/stats",
    response_model=BoardStatsResponse,
    summary="Desk totals: per-column depth, pipeline value and win rate - فارسی",
)
async def board_stats_route(
    session: SessionDep,
    _license: LicenseGuard,
    # The header sits on the same surface as the cards, so it is gated exactly
    # like the board feed: revenue per column is deal-flow data.
    workspace: ActiveAgencyDep,
) -> BoardStatsResponse:
    principal, membership, agency = workspace
    _role, membership_role = _workspace_actor_context(principal, membership)
    actor_user_id = await _resolve_actor_user(session, principal) if membership_role == "junior" else None
    global_admin = membership.role.upper() == "GLOBAL_ADMIN"
    visible_property_ids = None if global_admin else await _visible_crm_property_ids(session, agency=agency, principal=principal)
    stats = await crm_service.board_stats(
        session, agency_id=None if global_admin else str(agency.id), property_ids=visible_property_ids,
        assigned_user_id=actor_user_id,
        assigned_subject=principal.subject if membership_role == "junior" else None,
    )
    return BoardStatsResponse(
        total=stats.total,
        columns=[
            StageStat(
                stage=column.stage,
                count=column.count,
                total_value=column.total_value,
            )
            for column in stats.columns
        ],
        lost=stats.lost,
        bargains=stats.bargains,
        open_value=stats.open_value,
        closed_value=stats.closed_value,
        conversion_pct=stats.conversion_pct,
    )


@router.post(
    "/leads",
    response_model=LeadCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Open a lead card for an existing listing (idempotent per property) - لیست",
)
async def create_lead_route(
    payload: LeadCreateRequest,
    session: SessionDep,
    workspace: ActiveAgencyDep,
    _license: LicenseGuard,
) -> LeadCreateResponse:
    """Put a listing on the desk.

    Idempotent per property, so a double-click or a retried request returns the
    card that already exists instead of stacking a duplicate. That mirrors
    ``crm_service.create_lead_for_property``, which ingestion also calls.
    """
    principal, membership, agency = workspace
    _role, membership_role = _workspace_actor_context(principal, membership)
    prop = await session.get(Property, payload.property_id)
    if prop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "property_not_found",
                "message": "ملکی با این شناسه یافت نشد.",
            },
        )
    if not await _property_visible_to_workspace(
        session, prop, agency=agency, principal=principal, permission_name="view_summary"
    ):
        raise HTTPException(status_code=404, detail={"error": "property_not_found"})

    already = (
        await session.exec(
            select(CrmLead).where(
                CrmLead.property_id == payload.property_id,
                CrmLead.agency_id == str(agency.id),
            )
        )
    ).first()

    actor_user_id = await _resolve_actor_user(session, principal)
    assigned_user_id, assigned_subject = await _resolve_lead_assignee(
        session, payload=payload, principal=principal, agency=agency,
        membership_role=membership_role, actor_user_id=actor_user_id,
    )

    lead = await crm_service.create_lead_for_property(
        session, prop, agency_id=str(agency.id), assigned_user_id=assigned_user_id,
        assigned_subject=assigned_subject or None,
    )
    await session.commit()

    if lead is None:  # pragma: no cover -- create_lead_for_property always returns
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "lead_not_created"},
        )

    return LeadCreateResponse(
        lead_id=lead.id, created=already is None, stage=lead.stage
    )


@router.get(
    "/leads/{lead_id}",
    response_model=LeadDetailResponse,
    summary="One lead with its full interaction timeline - فارسی",
)
async def get_lead_route(
    lead_id: uuid.UUID,
    session: SessionDep,
    _license: LicenseGuard,
    workspace: ActiveAgencyDep,
) -> LeadDetailResponse:
    principal, membership, agency = workspace
    _role, membership_role = _workspace_actor_context(principal, membership)
    actor_user_id = await _resolve_actor_user(session, principal)
    lead = await _load_lead(session, lead_id, str(agency.id))
    _require_lead_assignment(lead, principal=principal, membership_role=membership_role, actor_user_id=actor_user_id)
    prop = await session.get(Property, lead.property_id)
    if prop is None or not await _property_visible_to_workspace(
        session, prop, agency=agency, principal=principal, permission_name="view_summary"
    ):
        raise HTTPException(status_code=404, detail={"error": "lead_not_found"})
    views = await crm_service.list_leads(session, agency_id=str(agency.id), property_ids={lead.property_id}, limit=1)
    view = next((v for v in views if v.id == lead.id), None)
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "lead_not_found"},
        )
    return LeadDetailResponse(
        lead=_to_summary(view), timeline=await _timeline(session, lead_id)
    )


@router.post(
    "/leads/{lead_id}/delete",
    response_model=LeadDeleteResponse,
    summary="Permanently purge a lead and its timeline (governor role only) - فارسی",
)
async def delete_lead_route(
    lead_id: uuid.UUID,
    payload: LeadDeleteRequest,
    session: SessionDep,
    workspace: ActiveAgencyDep,
    _license: LicenseGuard,
) -> LeadDeleteResponse:
    """Erase a lead for good.

    The *preferred* removal is moving the card to ``LOST_ARCHIVED``, which keeps
    the negotiation history and can be undone. This is the escape hatch for a
    card created by mistake, so it is deliberately hard to trigger:

    * a ``confirm`` flag must be set -- a bare DELETE with no body is a 422, so a
      stray client cannot purge deal history;
    * it requires a data-governor role, the same gate that covers merging
      duplicates and overriding the valuation engine.

    The underlying ``property`` row is untouched: only the lead and its
    timeline go away, so the listing stays in the inventory.
    """
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "confirmation_required",
                "message": "برای حذف دائمی باید تأیید صریح ارسال شود.",
            },
        )

    principal, membership, agency = workspace
    role, _membership_role = _workspace_actor_context(principal, membership)
    if role not in DATA_GOVERNOR_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "delete_not_permitted",
                "message": "حذف دائمی لید تنها با نقش ناظر یا مدیر ممکن است.",
            },
        )

    lead = await _load_lead(session, lead_id, str(agency.id))

    # Delete children first: LeadInteraction carries a FK to the lead, so
    # removing the parent first would either fail or leave orphans depending on
    # the session's flush order.
    events = (
        await session.exec(select(LeadInteraction).where(LeadInteraction.lead_id == lead_id))
    ).all()
    for event in events:
        await session.delete(event)

    await session.delete(lead)
    await session.commit()

    return LeadDeleteResponse(lead_id=lead_id, deleted_interactions=len(events))


@router.patch(
    "/leads/{lead_id}/stage",
    response_model=LeadDetailResponse,
    summary="Move a card to the next column (illegal moves return 409) - فارسی",
)
async def change_stage_route(
    lead_id: uuid.UUID,
    payload: StageChangeRequest,
    session: SessionDep,
    _license: LicenseGuard,
    workspace: ActiveAgencyDep,
) -> LeadDetailResponse:
    principal, membership, agency = workspace
    role, membership_role = _workspace_actor_context(principal, membership)
    actor_user_id = await _resolve_actor_user(session, principal)
    lead = await _load_lead(session, lead_id, str(agency.id))
    _require_lead_assignment(lead, principal=principal, membership_role=membership_role, actor_user_id=actor_user_id)
    prop = await session.get(Property, lead.property_id)
    if prop is None or not await _property_visible_to_workspace(
        session, prop, agency=agency, principal=principal, permission_name="allow_negotiation"
    ):
        raise HTTPException(status_code=403, detail={"error": "share_negotiation_not_permitted"})
    try:
        await crm_service.move_lead(
            session, lead, payload.target_stage, role=role,
            actor_user_id=actor_user_id, note=payload.note
        )
    except crm_service.InvalidTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "invalid_stage_transition", "message": str(exc)},
        ) from exc
    except crm_service.TransitionNotPermitted as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "transition_not_permitted", "message": str(exc)},
        ) from exc

    await session.commit()
    return await get_lead_route(lead_id, session, _license, workspace)


@router.post(
    "/leads/{lead_id}/events",
    response_model=InteractionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Append a timeline event (VISIT_EVENT carries scheduled_at) - فارسی",
)
async def add_interaction_route(
    lead_id: uuid.UUID,
    payload: InteractionRequest,
    session: SessionDep,
    _license: LicenseGuard,
    workspace: ActiveAgencyDep,
) -> InteractionResponse:
    principal, membership, agency = workspace
    _role, membership_role = _workspace_actor_context(principal, membership)
    actor_user_id = await _resolve_actor_user(session, principal)
    lead = await _load_lead(session, lead_id, str(agency.id))
    _require_lead_assignment(lead, principal=principal, membership_role=membership_role, actor_user_id=actor_user_id)
    prop = await session.get(Property, lead.property_id)
    required_share_permission = "allow_visit_request" if payload.interaction_type.value == "VISIT_EVENT" else "allow_notes"
    if prop is None or not await _property_visible_to_workspace(
        session, prop, agency=agency, principal=principal, permission_name=required_share_permission
    ):
        raise HTTPException(status_code=403, detail={"error": "share_action_not_permitted"})
    try:
        event = await crm_service.log_interaction(
            session,
            lead,
            interaction_type=payload.interaction_type,
            actor_user_id=actor_user_id,
            scheduled_at=payload.scheduled_at,
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_interaction", "message": str(exc)},
        ) from exc

    await session.commit()
    return InteractionResponse(
        id=event.id,
        interaction_type=event.interaction_type,
        scheduled_at=event.scheduled_at,
        note=event.note,
        created_at=event.created_at,
    )


@router.get(
    "/pii/quota",
    response_model=QuotaStatusResponse,
    summary="Remaining daily owner-contact reveals for the acting tier - فارسی",
)
async def quota_route(
    session: SessionDep,
    _license: LicenseGuard,
    workspace: ActiveAgencyDep,
) -> QuotaStatusResponse:
    principal, membership, _agency = workspace
    role, _membership_role = _workspace_actor_context(principal, membership)
    if principal.pii_denied or role not in pii_vault.PII_READER_ROLES:
        raise HTTPException(status_code=403, detail={"error": "pii_role_not_permitted"})
    actor_id = await _resolve_actor_user(session, principal)
    remaining = await pii_vault.remaining_quota(session, actor_id, principal.saas_tier)
    return QuotaStatusResponse(tier=principal.saas_tier, remaining=remaining)


@router.post(
    "/properties/{property_id}/reveal-contact",
    response_model=PiiRevealResponse,
    summary="Decrypt the owner phone — role + quota gated, always audited - فارسی",
)
async def reveal_contact_route(
    property_id: uuid.UUID,
    payload: PiiRevealRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    _license: LicenseGuard,
    workspace: ActiveAgencyDep,
) -> PiiRevealResponse:
    principal, membership, agency = workspace
    role, membership_role = _workspace_actor_context(principal, membership)
    if principal.pii_denied:
        raise HTTPException(status_code=403, detail={"error": "pii_role_denied"})
    if role in {UserRole.ADMIN, UserRole.SUPERVISOR} and len(payload.reason.strip()) < 12:
        raise HTTPException(status_code=422, detail={"error": "pii_audit_reason_required", "message": "برای دسترسی نظارتی دلیل حداقل ۱۲ نویسه‌ای ثبت کنید."})
    actor_id = await _resolve_actor_user(session, principal)
    cipher = PiiCipher.from_key_file(settings.resolve_path(settings.pii_key_file))

    lead = (await session.exec(select(CrmLead).where(
        CrmLead.property_id == property_id,
        CrmLead.agency_id == str(agency.id),
    ))).first()
    if lead is None:
        raise HTTPException(status_code=404, detail={"error": "lead_not_found"})
    _require_lead_assignment(
        lead, principal=principal, membership_role=membership_role,
        actor_user_id=actor_id, require_senior_assignment=True,
    )
    prop = await session.get(Property, property_id)
    if prop is None or not await _property_visible_to_workspace(
        session, prop, agency=agency, principal=principal, permission_name="show_owner_phone"
    ):
        raise HTTPException(status_code=403, detail={"error": "share_owner_contact_not_permitted"})

    try:
        result = await pii_vault.reveal_owner_phone(
            session,
            property_id=property_id,
            actor_user_id=actor_id,
            role=role,
            tier=principal.saas_tier,
            cipher=cipher,
            agency_id=agency.id,
            pii_denied=principal.pii_denied,
            client_ip=request.client.host if request.client else "",
            reason=payload.reason,
        )
    except pii_vault.PiiAccessDenied as exc:
        # The service already wrote the denied-attempt audit row; committing here
        # keeps it visible to a supervisor.
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": exc.reason, "message": exc.message},
        ) from exc

    await session.commit()
    return PiiRevealResponse(
        property_id=property_id,
        owner_name=result.owner_name,
        owner_phone=result.owner_phone,
        tier=result.tier,
        remaining_quota=result.remaining_quota,
    )


@router.get(
    "/pii/audit",
    response_model=list[PiiAccessLogEntry],
    summary="Supervisor view of the owner-PII access trail - فارسی",
)
async def pii_audit_route(
    session: SessionDep,
    _license: LicenseGuard,
    workspace: ActiveAgencyDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[PiiAccessLogEntry]:
    principal, membership, agency = workspace
    role, _membership_role = _workspace_actor_context(principal, membership)
    # Audit inspection is a governance privilege, not a desk feature.
    if role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "role_not_permitted",
                "message": "مشاهدهٔ لاگ ممیزی تنها برای ناظر یا مدیر ارشد مجاز است.",
            },
        )

    rows = (
        await session.exec(
            select(OwnerAccessLog)
            .where(OwnerAccessLog.agency_id == agency.id)
            .order_by(OwnerAccessLog.created_at.desc())  # type: ignore[arg-type]
            .limit(limit)
        )
    ).all()
    return [
        PiiAccessLogEntry(
            id=row.id,
            user_id=row.user_id,
            property_id=row.property_id,
            action=row.action,
            allowed=row.allowed,
            reason=row.reason,
            client_ip=row.client_ip,
            created_at=row.created_at,
        )
        for row in rows
    ]
