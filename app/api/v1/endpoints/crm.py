"""Phase 5 CRM endpoints: the five-column board, stage moves and the timeline.

Every route is licence-gated like the rest of the paid surface. Role/tier
resolution currently reads the ``X-User-Role`` / ``X-SaaS-Tier`` headers because
node authentication is still the licence guard; ``_actor_context`` is the single
seam to swap in real session data once OIDC/Clerk lands.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlmodel import select

from app.api.deps import LicenseGuard, Principal, PrincipalDep, SessionDep, SettingsDep
from app.core.crypto import PiiCipher
from app.core.identity import BOOTSTRAP_SUBJECT, ROLE_ORDER
from app.models import CrmLead, LeadInteraction, OwnerAccessLog, Property
from app.models.enums import (
    DATA_GOVERNOR_ROLES,
    LeadStage,
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


async def _load_lead(session: SessionDep, lead_id: uuid.UUID) -> CrmLead:
    lead = await session.get(CrmLead, lead_id)
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "lead_not_found"},
        )
    return lead


def _to_summary(view: crm_service.LeadView) -> LeadSummary:
    return LeadSummary(
        id=view.id,
        property_id=view.property_id,
        stage=view.stage,
        priority=view.priority,
        assigned_user_id=view.assigned_user_id,
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
    _principal: PrincipalDep,
    stage: list[LeadStage] | None = Query(default=None),
    bargains_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
) -> LeadListResponse:
    views = await crm_service.list_leads(
        session, stages=stage, bargains_only=bargains_only, limit=limit
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
    _principal: PrincipalDep,
) -> BoardStatsResponse:
    stats = await crm_service.board_stats(session)
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
    principal: PrincipalDep,
    _license: LicenseGuard,
) -> LeadCreateResponse:
    """Put a listing on the desk.

    Idempotent per property, so a double-click or a retried request returns the
    card that already exists instead of stacking a duplicate. That mirrors
    ``crm_service.create_lead_for_property``, which ingestion also calls.
    """
    prop = await session.get(Property, payload.property_id)
    if prop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "property_not_found",
                "message": "ملکی با این شناسه یافت نشد.",
            },
        )

    already = (
        await session.exec(
            select(CrmLead).where(CrmLead.property_id == payload.property_id)
        )
    ).first()

    assigned = payload.assigned_user_id
    if assigned is None:
        assigned = await _resolve_actor_user(session, principal)

    lead = await crm_service.create_lead_for_property(
        session, prop, assigned_user_id=assigned
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
) -> LeadDetailResponse:
    lead = await _load_lead(session, lead_id)
    views = await crm_service.list_leads(session, limit=500)
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
    principal: PrincipalDep,
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

    role, _tier = _actor_context(principal)
    if role not in DATA_GOVERNOR_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "delete_not_permitted",
                "message": "حذف دائمی لید تنها با نقش ناظر یا مدیر ممکن است.",
            },
        )

    lead = await _load_lead(session, lead_id)

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
    principal: PrincipalDep,
) -> LeadDetailResponse:
    role, _tier = _actor_context(principal)
    lead = await _load_lead(session, lead_id)
    try:
        await crm_service.move_lead(
            session, lead, payload.target_stage, role=role, note=payload.note
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
    return await get_lead_route(lead_id, session, _license)


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
) -> InteractionResponse:
    lead = await _load_lead(session, lead_id)
    try:
        event = await crm_service.log_interaction(
            session,
            lead,
            interaction_type=payload.interaction_type,
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
    principal: PrincipalDep,
) -> QuotaStatusResponse:
    _role, tier = _actor_context(principal)
    actor_id = await _resolve_actor_user(session, principal)
    remaining = await pii_vault.remaining_quota(session, actor_id, tier)
    return QuotaStatusResponse(tier=tier, remaining=remaining)


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
    principal: PrincipalDep,
) -> PiiRevealResponse:
    role, tier = _actor_context(principal)
    actor_id = await _resolve_actor_user(session, principal)
    cipher = PiiCipher.from_key_file(settings.resolve_path(settings.pii_key_file))

    try:
        result = await pii_vault.reveal_owner_phone(
            session,
            property_id=property_id,
            actor_user_id=actor_id,
            role=role,
            tier=tier,
            cipher=cipher,
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
    principal: PrincipalDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[PiiAccessLogEntry]:
    role, _tier = _actor_context(principal)
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

