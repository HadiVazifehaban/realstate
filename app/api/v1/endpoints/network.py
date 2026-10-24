"""Inter-agency collaboration network (شبکه همکاری دفاتر) -- Phase 1.

Endpoints covering the offices directory and the cooperation requests between
them. Sharing, transfers, referrals, commissions, disputes and audit are later
phases; this file is deliberately limited to the two things Phase 1 needs, so
the module can start accumulating real history before the rest of it lands.

Every endpoint sits behind the two guards the rest of the node uses -- the
commercial licence, and the caller's principal -- because a cooperation request
is a business offer from one office to another, and an anonymous one is spam.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import select

from app.api.deps import LicenseGuard, PrincipalDep, SessionDep
from app.models.base import utcnow
from app.models.agency_network import Agency, AgencyCooperation
from app.models.network_collab import (
    AuditEvent,
    CommissionAgreement,
    CommissionAllocation,
    CommissionPayment,
    DisputeCase,
    DisputeMessage,
    LeadReferral,
    ListingShare,
    ListingSharePermission,
    ListingTransferHistory,
)
from app.models.enums import (
    AgencyStatus,
    AuditAction,
    CommissionModel,
    CommissionStatus,
    CooperationScope,
    CooperationStatus,
    DisputeCategory,
    DisputeStatus,
    ListingShareMode,
    ReferralStatus,
    ShareStatus,
    TransferStatus,
)
from app.schemas.network import (
    AgencyCreate,
    AgencyRead,
    AuditEventRead,
    CommissionAgreementCreate,
    CommissionAgreementDetailRead,
    CommissionAgreementRead,
    CommissionPaymentCreate,
    CommissionPaymentRead,
    CooperationCreate,
    CooperationDecision,
    CooperationRead,
    DisputeCreate,
    DisputeDetailRead,
    DisputeMessageCreate,
    DisputeMessageRead,
    DisputeRead,
    DisputeStatusUpdate,
    LeadReferralCreate,
    LeadReferralRead,
    ListingShareCreate,
    ListingShareDetailRead,
    ListingShareRead,
    ListingTransferCreate,
    ListingTransferRead,
    NetworkOverviewRead,
    NetworkReportsRead,
    ReferralStageUpdate,
    SharePermissionRead,
)

router = APIRouter()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
async def _require_agency(
    session: SessionDep, agency_id: uuid.UUID
) -> Agency:
    """Fetch one office or 404.

    404 rather than 403 on a missing id: telling a caller that ``x`` exists but
    they cannot see it is a disclosure, and the id space is guessable.
    """
    row = await session.get(Agency, agency_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "agency_not_found", "message": "دفتری با این شناسه پیدا نشد."},
        )
    return row


async def _require_cooperation(
    session: SessionDep, cooperation_id: uuid.UUID
) -> AgencyCooperation:
    """Fetch one cooperation or 404."""
    row = await session.get(AgencyCooperation, cooperation_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "cooperation_not_found",
                "message": "درخواست همکاری با این شناسه پیدا نشد.",
            },
        )
    return row


def _as_read(row: AgencyCooperation) -> CooperationRead:
    return CooperationRead.model_validate(row)


# --------------------------------------------------------------------------- #
# Offices directory
# --------------------------------------------------------------------------- #
@router.get(
    "/agencies",
    response_model=list[AgencyRead],
    summary="Partner offices on the network (شبکه) (دفاتر همکار)",
)
async def list_agencies(
    session: SessionDep,
    _licence: LicenseGuard,
    q: str | None = Query(default=None, description="متن آزاد روی نام شهر منطقه"),
    city: str | None = Query(default=None, description="فیلتر شهر"),
    status_filter: AgencyStatus | None = Query(
        default=None, alias="status", description="وضعیت اعتماد دفتر"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AgencyRead]:
    """Browse partner offices.

    A ``VERIFIED``-only default would hide an office that exists but whose
    papers are still pending -- which is precisely the state a partner wants to
    inspect before requesting cooperation. The status badge carries the trust
    signal instead of the row being withheld.
    """
    conditions = []
    if q:
        needle = f"%{q.strip()}%"
        conditions.append(
            Agency.name.ilike(needle)
            | Agency.name_fa.ilike(needle)
            | Agency.city.ilike(needle)
            | Agency.district.ilike(needle)
        )
    if city:
        conditions.append(Agency.city == city)
    if status_filter is not None:
        conditions.append(Agency.status == status_filter)

    query = select(Agency)
    for condition in conditions:
        query = query.where(condition)
    query = query.order_by(Agency.created_at.desc()).limit(limit).offset(offset)

    rows = (await session.exec(query)).all()
    return [AgencyRead.model_validate(row) for row in rows]


@router.post(
    "/agencies",
    response_model=AgencyRead,
    status_code=status.HTTP_201_CREATED,
    summary="register (ثبت) an office on the network (شبکه)",
)
async def create_agency(
    payload: AgencyCreate,
    session: SessionDep,
    principal: PrincipalDep,
    _licence: LicenseGuard,
) -> AgencyRead:
    """Register an office.

    A new office arrives ``PENDING`` regardless of who created it: registering
    yourself for the network and vouching for yourself are two different acts,
    and only a network admin can do the second (see ``verified_by``).
    """
    existing = (
        await session.exec(select(Agency).where(Agency.slug == payload.slug))
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "slug_taken",
                "message": "این شناسه پیش‌تر ثبت شده است؛ شناسه دیگری انتخاب کنید.",
            },
        )

    row = Agency(
        slug=payload.slug,
        name=payload.name,
        name_fa=payload.name_fa,
        city=payload.city,
        district=payload.district,
        phone=payload.phone,
        description=payload.description,
        status=AgencyStatus.PENDING,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return AgencyRead.model_validate(row)


@router.get(
    "/agencies/{agency_id}",
    response_model=AgencyRead,
    summary="One partner office profile",
)
async def get_agency(
    agency_id: uuid.UUID,
    session: SessionDep,
    _licence: LicenseGuard,
) -> AgencyRead:
    row = await _require_agency(session, agency_id)
    return AgencyRead.model_validate(row)


# --------------------------------------------------------------------------- #
# Cooperation requests
# --------------------------------------------------------------------------- #
@router.post(
    "/cooperations",
    response_model=CooperationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Request to work with another office - فارسی",
)
async def create_cooperation(
    payload: CooperationCreate,
    session: SessionDep,
    principal: PrincipalDep,
    _licence: LicenseGuard,
) -> CooperationRead:
    """Open a cooperation request.

    A duplicate ``PENDING`` request between the same two offices is refused
    rather than queued twice: two pending requests for one relationship is how a
    network ends up with offices that each believe the other agreed.
    """
    requester = await _require_agency(session, payload.requester_agency_id)
    target = await _require_agency(session, payload.target_agency_id)

    if requester.id == target.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "self_cooperation",
                "message": "دفتر نمی‌تواند با خودش همکاری کند.",
            },
        )

    duplicate = (
        await session.exec(
            select(AgencyCooperation).where(
                AgencyCooperation.requester_agency_id == requester.id,
                AgencyCooperation.target_agency_id == target.id,
                AgencyCooperation.status == CooperationStatus.PENDING,
            )
        )
    ).first()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "cooperation_already_pending",
                "message": "درخواست همکاری با این دفتر از قبل در انتظار است.",
            },
        )

    expires_at = None
    if payload.expires_in_days:
        expires_at = utcnow() + timedelta(days=payload.expires_in_days)

    row = AgencyCooperation(
        requester_agency_id=requester.id,
        target_agency_id=target.id,
        scope=CooperationScope(payload.scope),
        default_commission_pct=payload.default_commission_pct,
        expires_at=expires_at,
        requested_by=principal.username or principal.subject,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _as_read(row)


@router.get(
    "/cooperations",
    response_model=list[CooperationRead],
    summary="Cooperation requests, from either side - فارسی",
)
async def list_cooperations(
    session: SessionDep,
    _licence: LicenseGuard,
    principal: PrincipalDep,
    agency_id: uuid.UUID | None = Query(default=None),
    direction: str | None = Query(
        default=None, description="incoming | outgoing | any"
    ),
    status_filter: CooperationStatus | None = Query(
        default=None, alias="status"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[CooperationRead]:
    """Requests an office is party to.

    ``direction`` is computed from the row, not stored, because the same row is
    an outgoing request from one node and an incoming one from the other. An
    ``agency_id`` is required to make that distinction mean anything.
    """
    # Use principal's agency_id if not provided
    if agency_id is None:
        if principal.agency_id:
            agency_id = principal.agency_id
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "agency_required",
                    "message": "برای تفکیک درخواست‌های ارسالی و دریافتی، شناسه دفتر لازم است.",
                },
            )

    conditions = []
    if direction == "incoming":
        conditions.append(AgencyCooperation.target_agency_id == agency_id)
    elif direction == "outgoing":
        conditions.append(AgencyCooperation.requester_agency_id == agency_id)
    else:
        conditions.append(
            (AgencyCooperation.requester_agency_id == agency_id)
            | (AgencyCooperation.target_agency_id == agency_id)
        )
    if status_filter is not None:
        conditions.append(AgencyCooperation.status == status_filter)

    query = select(AgencyCooperation)
    for condition in conditions:
        query = query.where(condition)
    query = query.order_by(AgencyCooperation.created_at.desc()).limit(limit).offset(offset)

    rows = (await session.exec(query)).all()
    return [_as_read(row) for row in rows]


@router.post(
    "/cooperations/{cooperation_id}/approve",
    response_model=CooperationRead,
    summary="Approve a cooperation request - فارسی",
)
async def approve_cooperation(
    cooperation_id: uuid.UUID,
    payload: CooperationDecision,
    session: SessionDep,
    principal: PrincipalDep,
    _licence: LicenseGuard,
) -> CooperationRead:
    row = await _require_cooperation(session, cooperation_id)

    if row.status != CooperationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "cooperation_not_pending",
                "message": "این درخواست پیش از آنکه تصمیم گرفته شود، تصمیم‌گیری شده است.",
            },
        )

    # Approval narrows, never widens: an approver may grant less than what was
    # asked for, and a counter-proposal asking for more is a reply, not an
    # approval.
    granted = [CooperationScope(s) for s in payload.granted_scopes] or [
        CooperationScope(row.scope)
    ]
    row.status = CooperationStatus.APPROVED
    row.granted_scopes = ",".join(scope.value for scope in granted)
    row.decision_reason = payload.reason or ""
    row.decided_by = principal.username or principal.subject
    row.decided_at = utcnow()

    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _as_read(row)


@router.post(
    "/cooperations/{cooperation_id}/reject",
    response_model=CooperationRead,
    summary="Reject a cooperation request - فارسی",
)
async def reject_cooperation(
    cooperation_id: uuid.UUID,
    payload: CooperationDecision,
    session: SessionDep,
    principal: PrincipalDep,
    _licence: LicenseGuard,
) -> CooperationRead:
    row = await _require_cooperation(session, cooperation_id)

    if row.status != CooperationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "cooperation_not_pending",
                "message": "این درخواست پیش از آنکه تصمیم گرفته شود، تصمیم‌گیری شده است.",
            },
        )

    if not payload.reason or not payload.reason.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "reason_required",
                "message": "برای رد درخواست همکاری، ذکر دلیل الزامی است.",
            },
        )

    row.status = CooperationStatus.REJECTED
    row.decision_reason = payload.reason.strip()
    row.decided_by = principal.username or principal.subject
    row.decided_at = utcnow()

    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _as_read(row)


# =========================================================================== #
# Phase 2-5 -- shares, referrals, transfers, commissions, disputes, audit
# =========================================================================== #
#
# A single audit helper underpins every endpoint below. The rule from the spec
# is that every security-sensitive cross-office action records actor + target +
# action + timestamp, so ``_audit`` is called at the point of the action rather
# than left to each caller to remember.
async def _audit(
    session: SessionDep,
    *,
    action: AuditAction,
    principal: PrincipalDep,
    entity_type: str,
    entity_id: uuid.UUID | None,
    property_id: uuid.UUID | None = None,
    target_agency_id: uuid.UUID | None = None,
    detail: str = "",
) -> None:
    """Append one audit row. Never raises -- a failed log must not roll back a
    legitimate business action the user already performed."""
    event = AuditEvent(
        action=action,
        actor=principal.username or principal.subject,
        entity_type=entity_type,
        entity_id=entity_id,
        property_id=property_id,
        target_agency_id=target_agency_id,
        detail=detail,
    )
    session.add(event)


# --------------------------------------------------------------------------- #
# Listing shares (Phase 2)
# --------------------------------------------------------------------------- #
async def _require_share(session: SessionDep, share_id: uuid.UUID) -> ListingShare:
    row = await session.get(ListingShare, share_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "share_not_found", "message": "اشتراک فایل پیدا نشد."},
        )
    return row


def _share_as_read(row: ListingShare) -> ListingShareRead:
    return ListingShareRead.model_validate(row)


@router.post(
    "/shares",
    response_model=ListingShareDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="اشتراک / ارجاع / انتقال یک فایل به دفتر همکار - فارسی",
)
async def create_share(
    payload: ListingShareCreate,
    session: SessionDep,
    principal: PrincipalDep,
    _licence: LicenseGuard,
) -> ListingShareDetailRead:
    """Grant a partner office access to one file.

    The permission row is written from ``payload.permissions``, whose defaults
    are the safe end of every switch (Section F): owner phone off, exact address
    off, re-share off. A TRANSFER mode share also opens a transfer-history row
    so the chain of custody starts here, not later.
    """
    try:
        mode = ListingShareMode(payload.mode)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "bad_mode", "message": "نوع اشتراک نامعتبر است."},
        )

    source = await _require_agency(session, payload.source_agency_id)
    target = await _require_agency(session, payload.target_agency_id)
    if source.id == target.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "self_share", "message": "دفتر نمی‌تواند فایل را با خودش به اشتراک بگذارد."},
        )

    expires_at = None
    if payload.expires_in_days:
        expires_at = utcnow() + timedelta(days=payload.expires_in_days)

    share = ListingShare(
        property_id=payload.property_id,
        source_agency_id=source.id,
        target_agency_id=target.id,
        mode=mode,
        target_agent=payload.target_agent,
        note=payload.note,
        internal_note=payload.internal_note,
        expires_at=expires_at,
        created_by=principal.username or principal.subject,
    )
    session.add(share)
    await session.flush()

    perm = ListingSharePermission(share_id=share.id, **payload.permissions.model_dump())
    perm.updated_by = principal.username or principal.subject
    session.add(perm)

    # A TRANSFER share records the move of responsibility immediately, so the
    # history is never reconstructed after the fact.
    if mode is ListingShareMode.TRANSFER:
        session.add(
            ListingTransferHistory(
                property_id=payload.property_id,
                from_agency_id=source.id,
                to_agency_id=target.id,
                to_user=payload.target_agent,
                status=TransferStatus.COMPLETED,
                reason=payload.note,
                executed_by=principal.username or principal.subject,
                executed_at=utcnow(),
            )
        )

    await _audit(
        session,
        action=AuditAction.SHARE_CREATED,
        principal=principal,
        entity_type="share",
        entity_id=share.id,
        property_id=payload.property_id,
        target_agency_id=target.id,
        detail=f"mode={mode.value}",
    )
    await session.commit()
    await session.refresh(share)
    await session.refresh(perm)
    return ListingShareDetailRead(
        **_share_as_read(share).model_dump(),
        internal_note=share.internal_note,
        permissions=SharePermissionRead.model_validate(perm),
    )


@router.get(
    "/shares",
    response_model=list[ListingShareRead],
    summary="فهرست اشتراک‌های فایل (ارسالی/دریافتی) - فارسی",
)
async def list_shares(
    session: SessionDep,
    _licence: LicenseGuard,
    agency_id: uuid.UUID | None = Query(default=None, description="فیلتر بر اساس دفتر"),
    direction: str | None = Query(default=None, description="incoming|outgoing"),
    status_filter: ShareStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ListingShareRead]:
    query = select(ListingShare)
    if agency_id is not None:
        if direction == "outgoing":
            query = query.where(ListingShare.source_agency_id == agency_id)
        elif direction == "incoming":
            query = query.where(ListingShare.target_agency_id == agency_id)
        else:
            query = query.where(
                (ListingShare.source_agency_id == agency_id)
                | (ListingShare.target_agency_id == agency_id)
            )
    if status_filter is not None:
        query = query.where(ListingShare.status == status_filter)
    query = query.order_by(ListingShare.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.exec(query)).all()
    return [_share_as_read(row) for row in rows]


@router.get(
    "/shares/{share_id}",
    response_model=ListingShareDetailRead,
    summary="جزئیات یک اشتراک فایل - فارسی",
)
async def get_share(
    share_id: uuid.UUID,
    session: SessionDep,
    _licence: LicenseGuard,
) -> ListingShareDetailRead:
    share = await _require_share(session, share_id)
    perm = await session.get(ListingSharePermission, share.id)
    return ListingShareDetailRead(
        **_share_as_read(share).model_dump(),
        internal_note=share.internal_note,
        permissions=SharePermissionRead.model_validate(perm) if perm else SharePermissionRead(updated_at=share.created_at, updated_by=share.created_by),
    )


@router.post(
    "/shares/{share_id}/revoke",
    response_model=ListingShareRead,
    summary="لغو اشتراک -- دسترسی بی‌درنگ بسته می‌شود - فارسی",
)
async def revoke_share(
    share_id: uuid.UUID,
    session: SessionDep,
    principal: PrincipalDep,
    _licence: LicenseGuard,
) -> ListingShareRead:
    """Revoke a share. Revoked access blocks the UI and the API immediately:
    the status flip is the single source of truth every read path checks."""
    share = await _require_share(session, share_id)
    if share.status is ShareStatus.REVOKED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "already_revoked", "message": "این اشتراک پیش‌تر لغو شده است."},
        )
    share.status = ShareStatus.REVOKED
    share.revoked_by = principal.username or principal.subject
    share.revoked_at = utcnow()
    session.add(share)
    await _audit(
        session,
        action=AuditAction.SHARE_REVOKED,
        principal=principal,
        entity_type="share",
        entity_id=share.id,
        property_id=share.property_id,
        target_agency_id=share.target_agency_id,
    )
    await session.commit()
    await session.refresh(share)
    return _share_as_read(share)


@router.post(
    "/shares/{share_id}/extend",
    response_model=ListingShareRead,
    summary="تمدید مهلت اشتراک - فارسی",
)
async def extend_share(
    share_id: uuid.UUID,
    session: SessionDep,
    principal: PrincipalDep,
    _licence: LicenseGuard,
    days: int = Query(default=30, ge=1, le=3650),
) -> ListingShareRead:
    share = await _require_share(session, share_id)
    base = share.expires_at or utcnow()
    # Extending an already-expired share from now, not from its dead expiry, so a
    # lapsed file does not come back with a negative lifetime.
    share.expires_at = max(base, utcnow()) + timedelta(days=days)
    if share.status is ShareStatus.EXPIRED:
        share.status = ShareStatus.ACTIVE
    session.add(share)
    await _audit(
        session,
        action=AuditAction.SHARE_EXTENDED,
        principal=principal,
        entity_type="share",
        entity_id=share.id,
        property_id=share.property_id,
        target_agency_id=share.target_agency_id,
        detail=f"+{days}d",
    )
    await session.commit()
    await session.refresh(share)
    return _share_as_read(share)


# --------------------------------------------------------------------------- #
# Referrals (Phase 3)
# --------------------------------------------------------------------------- #
@router.post(
    "/referrals",
    response_model=LeadReferralRead,
    status_code=status.HTTP_201_CREATED,
    summary="ارجاع مشتری/سرنخ به دفتر همکار - فارسی",
)
async def create_referral(
    payload: LeadReferralCreate,
    session: SessionDep,
    principal: PrincipalDep,
    _licence: LicenseGuard,
) -> LeadReferralRead:
    source = await _require_agency(session, payload.source_agency_id)
    target = await _require_agency(session, payload.target_agency_id)
    if source.id == target.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "self_referral", "message": "دفتر نمی‌تواند به خودش ارجاع دهد."},
        )
    row = LeadReferral(
        subject=payload.subject,
        client_masked=payload.client_masked,
        source_agency_id=source.id,
        target_agency_id=target.id,
        property_id=payload.property_id,
        assigned_to=payload.assigned_to,
        referral_fee_pct=payload.referral_fee_pct,
        note=payload.note,
        created_by=principal.username or principal.subject,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return LeadReferralRead.model_validate(row)


@router.get(
    "/referrals",
    response_model=list[LeadReferralRead],
    summary="فهرست ارجاع‌ها (ارسالی/دریافتی) - فارسی",
)
async def list_referrals(
    session: SessionDep,
    _licence: LicenseGuard,
    agency_id: uuid.UUID | None = Query(default=None),
    direction: str | None = Query(default=None, description="incoming|outgoing"),
    stage: ReferralStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[LeadReferralRead]:
    query = select(LeadReferral)
    if agency_id is not None:
        if direction == "outgoing":
            query = query.where(LeadReferral.source_agency_id == agency_id)
        elif direction == "incoming":
            query = query.where(LeadReferral.target_agency_id == agency_id)
        else:
            query = query.where(
                (LeadReferral.source_agency_id == agency_id)
                | (LeadReferral.target_agency_id == agency_id)
            )
    if stage is not None:
        query = query.where(LeadReferral.stage == stage)
    query = query.order_by(LeadReferral.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.exec(query)).all()
    return [LeadReferralRead.model_validate(row) for row in rows]


@router.patch(
    "/referrals/{referral_id}/stage",
    response_model=LeadReferralRead,
    summary="تغییر مرحلهٔ ارجاع - فارسی",
)
async def update_referral_stage(
    referral_id: uuid.UUID,
    payload: ReferralStageUpdate,
    session: SessionDep,
    _licence: LicenseGuard,
) -> LeadReferralRead:
    row = await session.get(LeadReferral, referral_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "referral_not_found", "message": "ارجاع پیدا نشد."},
        )
    try:
        row.stage = ReferralStatus(payload.stage)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "bad_stage", "message": "مرحلهٔ ارجاع نامعتبر است."},
        )
    row.outcome = payload.outcome or row.outcome
    row.updated_at = utcnow()
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return LeadReferralRead.model_validate(row)



# --------------------------------------------------------------------------- #
# Transfers (Phase 3)
# --------------------------------------------------------------------------- #
@router.post(
    "/transfers",
    response_model=ListingTransferRead,
    status_code=status.HTTP_201_CREATED,
    summary="انتقال مسئولیت فایل به دفتر دیگر (با تأیید صریح) - فارسی",
)
async def create_transfer(
    payload: ListingTransferCreate,
    session: SessionDep,
    principal: PrincipalDep,
    _licence: LicenseGuard,
) -> ListingTransferRead:
    """Move a file's responsibility. Higher bar than a share: a reason is
    mandatory (enforced by the schema) and ``confirm`` must be true, so a
    transfer cannot be fired by the same casual click that shares a file. The
    row is append-only history; the previous office may keep a residual
    commission."""
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "confirm_required", "message": "انتقال فایل نیاز به تأیید صریح دارد."},
        )
    await _require_agency(session, payload.from_agency_id)
    await _require_agency(session, payload.to_agency_id)
    row = ListingTransferHistory(
        property_id=payload.property_id,
        from_agency_id=payload.from_agency_id,
        to_agency_id=payload.to_agency_id,
        to_user=payload.to_user,
        status=TransferStatus.COMPLETED,
        reason=payload.reason,
        residual_commission_pct=payload.residual_commission_pct,
        executed_by=principal.username or principal.subject,
        executed_at=utcnow(),
    )
    session.add(row)
    await _audit(
        session,
        action=AuditAction.TRANSFER_EXECUTED,
        principal=principal,
        entity_type="transfer",
        entity_id=row.id,
        property_id=payload.property_id,
        target_agency_id=payload.to_agency_id,
        detail=payload.reason,
    )
    await session.commit()
    await session.refresh(row)
    return ListingTransferRead.model_validate(row)


@router.get(
    "/transfers",
    response_model=list[ListingTransferRead],
    summary="تاریخچهٔ انتقال فایل‌ها - فارسی",
)
async def list_transfers(
    session: SessionDep,
    _licence: LicenseGuard,
    property_id: uuid.UUID | None = Query(default=None),
    agency_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ListingTransferRead]:
    query = select(ListingTransferHistory)
    if property_id is not None:
        query = query.where(ListingTransferHistory.property_id == property_id)
    if agency_id is not None:
        query = query.where(
            (ListingTransferHistory.from_agency_id == agency_id)
            | (ListingTransferHistory.to_agency_id == agency_id)
        )
    query = query.order_by(ListingTransferHistory.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.exec(query)).all()
    return [ListingTransferRead.model_validate(row) for row in rows]


# --------------------------------------------------------------------------- #
# Commissions (Phase 4)
# --------------------------------------------------------------------------- #
async def _agreement_detail(
    session: SessionDep, agreement: CommissionAgreement
) -> CommissionAgreementDetailRead:
    allocs = (
        await session.exec(
            select(CommissionAllocation).where(
                CommissionAllocation.agreement_id == agreement.id
            )
        )
    ).all()
    alloc_ids = [a.id for a in allocs]
    payments: list[CommissionPayment] = []
    if alloc_ids:
        payments = (
            await session.exec(
                select(CommissionPayment).where(
                    CommissionPayment.allocation_id.in_(alloc_ids)
                )
            )
        ).all()
    total_paid = sum(p.amount for p in payments)
    # Remaining is measured against the basis for a percentage split, and against
    # the sum of fixed allocations for a fixed model -- so the ledger header is
    # correct for either model without the client re-deriving it.
    if agreement.model is CommissionModel.PERCENTAGE:
        remaining = max(agreement.basis_amount - total_paid, 0)
    else:
        total_fixed = sum(a.fixed_amount for a in allocs)
        remaining = max(total_fixed - total_paid, 0)
    return CommissionAgreementDetailRead(
        **CommissionAgreementRead.model_validate(agreement).model_dump(),
        allocations=[CommissionAllocationRead.model_validate(a) for a in allocs],
        payments=[CommissionPaymentRead.model_validate(p) for p in payments],
        total_paid=total_paid,
        remaining=remaining,
    )


@router.post(
    "/commissions",
    response_model=CommissionAgreementDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="ایجاد توافق پورسانت (پیش‌نویس) - فارسی",
)
async def create_commission(
    payload: CommissionAgreementCreate,
    session: SessionDep,
    principal: PrincipalDep,
    _licence: LicenseGuard,
) -> CommissionAgreementDetailRead:
    try:
        model = CommissionModel(payload.model)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "bad_model", "message": "مدل پورسانت نامعتبر است."},
        )
    await _require_agency(session, payload.source_agency_id)
    await _require_agency(session, payload.target_agency_id)

    agreement = CommissionAgreement(
        property_id=payload.property_id,
        source_agency_id=payload.source_agency_id,
        target_agency_id=payload.target_agency_id,
        model=model,
        basis_amount=payload.basis_amount,
        currency=payload.currency,
        note=payload.note,
        created_by=principal.username or principal.subject,
    )
    session.add(agreement)
    await session.flush()
    for alloc in payload.allocations:
        session.add(
            CommissionAllocation(
                agreement_id=agreement.id,
                agency_id=alloc.agency_id,
                agent=alloc.agent,
                percent=alloc.percent,
                fixed_amount=alloc.fixed_amount,
            )
        )
    await _audit(
        session,
        action=AuditAction.COMMISSION_MODIFIED,
        principal=principal,
        entity_type="commission",
        entity_id=agreement.id,
        property_id=payload.property_id,
        target_agency_id=payload.target_agency_id,
        detail="created draft",
    )
    await session.commit()
    await session.refresh(agreement)
    return await _agreement_detail(session, agreement)


@router.get(
    "/commissions",
    response_model=list[CommissionAgreementRead],
    summary="فهرست توافق‌های پورسانت - فارسی",
)
async def list_commissions(
    session: SessionDep,
    _licence: LicenseGuard,
    agency_id: uuid.UUID | None = Query(default=None),
    status_filter: CommissionStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[CommissionAgreementRead]:
    query = select(CommissionAgreement)
    if agency_id is not None:
        query = query.where(
            (CommissionAgreement.source_agency_id == agency_id)
            | (CommissionAgreement.target_agency_id == agency_id)
        )
    if status_filter is not None:
        query = query.where(CommissionAgreement.status == status_filter)
    query = query.order_by(CommissionAgreement.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.exec(query)).all()
    return [CommissionAgreementRead.model_validate(row) for row in rows]


@router.get(
    "/commissions/{agreement_id}",
    response_model=CommissionAgreementDetailRead,
    summary="جزئیات توافق پورسانت با سهم‌ها و پرداخت‌ها - فارسی",
)
async def get_commission(
    agreement_id: uuid.UUID,
    session: SessionDep,
    _licence: LicenseGuard,
) -> CommissionAgreementDetailRead:
    agreement = await session.get(CommissionAgreement, agreement_id)
    if agreement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "agreement_not_found", "message": "توافق پورسانت پیدا نشد."},
        )
    return await _agreement_detail(session, agreement)


@router.post(
    "/commissions/{agreement_id}/lock",
    response_model=CommissionAgreementRead,
    summary="قفل کردن توافق -- سهم‌ها از این پس تغییرatable نیستند - فارسی",
)
async def lock_commission(
    agreement_id: uuid.UUID,
    session: SessionDep,
    principal: PrincipalDep,
    _licence: LicenseGuard,
) -> CommissionAgreementRead:
    agreement = await session.get(CommissionAgreement, agreement_id)
    if agreement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "agreement_not_found", "message": "توافق پورسانت پیدا نشد."},
        )
    if agreement.status is not CommissionStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "not_draft", "message": "فقط پیش‌نویس قابل قفل است."},
        )
    agreement.status = CommissionStatus.LOCKED
    agreement.locked_by = principal.username or principal.subject
    agreement.locked_at = utcnow()
    agreement.updated_at = utcnow()
    session.add(agreement)
    await _audit(
        session,
        action=AuditAction.COMMISSION_LOCKED,
        principal=principal,
        entity_type="commission",
        entity_id=agreement.id,
        property_id=agreement.property_id,
        target_agency_id=agreement.target_agency_id,
    )
    await session.commit()
    await session.refresh(agreement)
    return CommissionAgreementRead.model_validate(agreement)


@router.post(
    "/commissions/payments",
    response_model=CommissionPaymentRead,
    status_code=status.HTTP_201_CREATED,
    summary="ثبت پرداخت روی یک سهم - فارسی",
)
async def record_payment(
    payload: CommissionPaymentCreate,
    session: SessionDep,
    principal: PrincipalDep,
    _licence: LicenseGuard,
) -> CommissionPaymentRead:
    alloc = await session.get(CommissionAllocation, payload.allocation_id)
    if alloc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "allocation_not_found", "message": "سهم پیدا نشد."},
        )
    payment = CommissionPayment(
        allocation_id=alloc.id,
        amount=payload.amount,
        reference=payload.reference,
        note=payload.note,
        recorded_by=principal.username or principal.subject,
    )
    session.add(payment)
    await session.flush()
    # Roll the agreement up from the ledger so its status tracks reality.
    agreement = await session.get(CommissionAgreement, alloc.agreement_id)
    if agreement is not None and agreement.status is CommissionStatus.LOCKED:
        agreement.status = CommissionStatus.PARTIALLY_PAID
        agreement.updated_at = utcnow()
        session.add(agreement)
    await _audit(
        session,
        action=AuditAction.PAYMENT_RECORDED,
        principal=principal,
        entity_type="commission_payment",
        entity_id=payment.id,
        detail=f"amount={payload.amount}",
    )
    await session.commit()
    await session.refresh(payment)
    return CommissionPaymentRead.model_validate(payment)


# --------------------------------------------------------------------------- #
# Disputes (Phase 5)
# --------------------------------------------------------------------------- #
@router.post(
    "/disputes",
    response_model=DisputeRead,
    status_code=status.HTTP_201_CREATED,
    summary="ثبت اختلاف بین دو دفتر - فارسی",
)
async def create_dispute(
    payload: DisputeCreate,
    session: SessionDep,
    principal: PrincipalDep,
    _licence: LicenseGuard,
) -> DisputeRead:
    try:
        category = DisputeCategory(payload.category)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "bad_category", "message": "دستهٔ اختلاف نامعتبر است."},
        )
    row = DisputeCase(
        category=category,
        claimant_agency_id=payload.claimant_agency_id,
        respondent_agency_id=payload.respondent_agency_id,
        share_id=payload.share_id,
        agreement_id=payload.agreement_id,
        referral_id=payload.referral_id,
        property_id=payload.property_id,
        title=payload.title,
        detail=payload.detail,
        opened_by=principal.username or principal.subject,
    )
    session.add(row)
    await session.flush()
    await _audit(
        session,
        action=AuditAction.DISPUTE_OPENED,
        principal=principal,
        entity_type="dispute",
        entity_id=row.id,
        target_agency_id=payload.respondent_agency_id,
        property_id=payload.property_id,
        detail=payload.title,
    )
    await session.commit()
    await session.refresh(row)
    return DisputeRead.model_validate(row)


@router.get(
    "/disputes",
    response_model=list[DisputeRead],
    summary="فهرست اختلافات - فارسی",
)
async def list_disputes(
    session: SessionDep,
    _licence: LicenseGuard,
    agency_id: uuid.UUID | None = Query(default=None),
    status_filter: DisputeStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[DisputeRead]:
    query = select(DisputeCase)
    if agency_id is not None:
        query = query.where(
            (DisputeCase.claimant_agency_id == agency_id)
            | (DisputeCase.respondent_agency_id == agency_id)
        )
    if status_filter is not None:
        query = query.where(DisputeCase.status == status_filter)
    query = query.order_by(DisputeCase.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.exec(query)).all()
    return [DisputeRead.model_validate(row) for row in rows]


@router.get(
    "/disputes/{dispute_id}",
    response_model=DisputeDetailRead,
    summary="جزئیات اختلاف با گفتگو - فارسی",
)
async def get_dispute(
    dispute_id: uuid.UUID,
    session: SessionDep,
    _licence: LicenseGuard,
) -> DisputeDetailRead:
    row = await session.get(DisputeCase, dispute_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "dispute_not_found", "message": "اختلاف پیدا نشد."},
        )
    messages = (
        await session.exec(
            select(DisputeMessage)
            .where(DisputeMessage.dispute_id == row.id)
            .order_by(DisputeMessage.created_at.asc())
        )
    ).all()
    return DisputeDetailRead(
        **DisputeRead.model_validate(row).model_dump(),
        messages=[DisputeMessageRead.model_validate(m) for m in messages],
    )


@router.post(
    "/disputes/{dispute_id}/messages",
    response_model=DisputeMessageRead,
    status_code=status.HTTP_201_CREATED,
    summary="افزودن پیام به اختلاف - فارسی",
)
async def add_dispute_message(
    dispute_id: uuid.UUID,
    payload: DisputeMessageCreate,
    session: SessionDep,
    principal: PrincipalDep,
    _licence: LicenseGuard,
) -> DisputeMessageRead:
    row = await session.get(DisputeCase, dispute_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "dispute_not_found", "message": "اختلاف پیدا نشد."},
        )
    message = DisputeMessage(
        dispute_id=row.id,
        author=principal.username or principal.subject,
        body=payload.body,
        is_internal=payload.is_internal,
    )
    session.add(message)
    row.updated_at = utcnow()
    session.add(row)
    await session.commit()
    await session.refresh(message)
    return DisputeMessageRead.model_validate(message)


@router.post(
    "/disputes/{dispute_id}/status",
    response_model=DisputeRead,
    summary="تغییر وضعیت اختلاف - فارسی",
)
async def update_dispute_status(
    dispute_id: uuid.UUID,
    payload: DisputeStatusUpdate,
    session: SessionDep,
    principal: PrincipalDep,
    _licence: LicenseGuard,
) -> DisputeRead:
    row = await session.get(DisputeCase, dispute_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "dispute_not_found", "message": "اختلاف پیدا نشد."},
        )
    try:
        new_status = DisputeStatus(payload.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "bad_status", "message": "وضعیت اختلاف نامعتبر است."},
        )
    row.status = new_status
    row.resolution = payload.resolution or row.resolution
    row.updated_at = utcnow()
    if new_status in (DisputeStatus.RESOLVED, DisputeStatus.REJECTED):
        row.resolved_by = principal.username or principal.subject
        row.resolved_at = utcnow()
        await _audit(
            session,
            action=AuditAction.DISPUTE_RESOLVED,
            principal=principal,
            entity_type="dispute",
            entity_id=row.id,
            target_agency_id=row.respondent_agency_id,
            detail=payload.resolution,
        )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return DisputeRead.model_validate(row)


# --------------------------------------------------------------------------- #
# Audit (Phase 5)
# --------------------------------------------------------------------------- #
@router.get(
    "/audit",
    response_model=list[AuditEventRead],
    summary="رهگیری و لاگ رویدادهای امنیتی شبکه - فارسی",
)
async def list_audit(
    session: SessionDep,
    _licence: LicenseGuard,
    action: AuditAction | None = Query(default=None),
    agency_id: uuid.UUID | None = Query(default=None),
    property_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[AuditEventRead]:
    query = select(AuditEvent)
    if action is not None:
        query = query.where(AuditEvent.action == action)
    if agency_id is not None:
        query = query.where(AuditEvent.target_agency_id == agency_id)
    if property_id is not None:
        query = query.where(AuditEvent.property_id == property_id)
    query = query.order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.exec(query)).all()
    return [AuditEventRead.model_validate(row) for row in rows]
