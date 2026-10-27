"""Aggregated network stats (overview + reports)."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlmodel import select

from app.api.deps import LicenseGuard, PrincipalDep, SessionDep
from app.models.agency_network import Agency, AgencyCooperation
from app.models.enums import (
    AgencyStatus,
    CommissionStatus,
    CooperationStatus,
    DisputeStatus,
    ReferralStatus,
    ShareStatus,
)
from app.models.network_collab import (
    AuditEvent,
    CommissionAgreement,
    CommissionAllocation,
    CommissionPayment,
    DisputeCase,
    LeadReferral,
    ListingShare,
    ListingTransferHistory,
)
from app.schemas.network import NetworkOverviewRead, NetworkReportsRead, ReportsByStatus

router = APIRouter()


def _report_agency(
    principal: PrincipalDep,
    agency_id: uuid.UUID | None = Query(default=None),
    legacy_agency_id: uuid.UUID | None = Query(default=None, alias="agencyId", deprecated=True),
) -> uuid.UUID:
    """Fail closed: route roles never imply cross-tenant financial authority.

    Personal report attribution is not defined across all these entities. Brokers
    cannot use an agency aggregate as a substitute for a personal report. No
    existing platform/billing permission grants global network-report access.
    """
    if not principal.realm_roles.intersection(
        {"ROLE_AGENCY_MANAGER", "ROLE_ADMIN", "ROLE_SUPERVISOR"}
    ):
        raise HTTPException(status_code=403, detail={
            "error": "agency_reports_required",
            "message": "گزارش تجمیعی دفتر فقط برای نقش مدیریتی مجاز است؛ گزارش شخصی هنوز فعال نیست.",
        })
    try:
        tenant = uuid.UUID(principal.tenant_id or "")
    except ValueError:
        raise HTTPException(status_code=403, detail={
            "error": "agency_required", "message": "دفتر معتبر برای گزارش لازم است.",
        }) from None
    if tenant.int == 0:
        raise HTTPException(status_code=403, detail={
            "error": "agency_required", "message": "دفتر معتبر برای گزارش لازم است.",
        })
    if agency_id is not None and legacy_agency_id is not None and agency_id != legacy_agency_id:
        raise HTTPException(status_code=422, detail={
            "error": "conflicting_agency_scope", "message": "پارامترهای دفتر باید یکسان باشند.",
        })
    if any(requested is not None and requested != tenant for requested in (agency_id, legacy_agency_id)):
        raise HTTPException(status_code=403, detail={
            "error": "agency_forbidden", "message": "گزارش دفتر دیگر مجاز نیست.",
        })
    return tenant


ReportAgencyDep = Annotated[uuid.UUID, Depends(_report_agency)]


def _sided(agency_id: uuid.UUID, *cols):
    return or_(*[c == agency_id for c in cols])


def _payments(agency_id: uuid.UUID):
    # Both predicates matter: a participant cannot read another beneficiary's
    # payments, and a malformed allocation must not grant access to another deal.
    return (
        select(func.coalesce(func.sum(CommissionPayment.amount), 0))
        .select_from(CommissionPayment)
        .join(CommissionAllocation, CommissionAllocation.id == CommissionPayment.allocation_id)
        .join(CommissionAgreement, CommissionAgreement.id == CommissionAllocation.agreement_id)
        .where(
            CommissionAllocation.agency_id == agency_id,
            _sided(agency_id, CommissionAgreement.source_agency_id, CommissionAgreement.target_agency_id),
        )
    )


async def _count(session, model, *conds):
    q = select(func.count()).select_from(model)
    for c in conds:
        if c is not None:
            q = q.where(c)
    return int((await session.exec(q)).one() or 0)


async def _group(session, model, col, *extra, labels=None):
    q = select(col, func.count()).select_from(model).group_by(col)
    for c in extra:
        if c is not None:
            q = q.where(c)
    rows = (await session.exec(q)).all()
    out: list[ReportsByStatus] = []
    for value, count in rows:
        key = value.value if hasattr(value, "value") else str(value)
        out.append(ReportsByStatus(status=key, label_fa=(labels or {}).get(key, key), count=int(count)))
    return sorted(out, key=lambda r: -r.count)


@router.get("/overview", response_model=NetworkOverviewRead)
async def network_overview(
    session: SessionDep,
    _licence: LicenseGuard,
    agency_id: ReportAgencyDep,
) -> NetworkOverviewRead:
    s_coop = _sided(agency_id, AgencyCooperation.requester_agency_id, AgencyCooperation.target_agency_id)
    s_share = _sided(agency_id, ListingShare.source_agency_id, ListingShare.target_agency_id)
    s_ref = _sided(agency_id, LeadReferral.source_agency_id, LeadReferral.target_agency_id)
    s_tr = _sided(agency_id, ListingTransferHistory.from_agency_id, ListingTransferHistory.to_agency_id)
    s_comm = _sided(agency_id, CommissionAgreement.source_agency_id, CommissionAgreement.target_agency_id)
    s_disp = _sided(agency_id, DisputeCase.claimant_agency_id, DisputeCase.respondent_agency_id)
    s_audit = _sided(agency_id, AuditEvent.actor_agency_id, AuditEvent.target_agency_id)
    open_ref = or_(LeadReferral.stage == ReferralStatus.SENT, LeadReferral.stage == ReferralStatus.VIEWED, LeadReferral.stage == ReferralStatus.ACCEPTED, LeadReferral.stage == ReferralStatus.IN_FOLLOW_UP)
    open_comm = or_(CommissionAgreement.status == CommissionStatus.DRAFT, CommissionAgreement.status == CommissionStatus.LOCKED, CommissionAgreement.status == CommissionStatus.PARTIALLY_PAID)
    open_disp = or_(DisputeCase.status == DisputeStatus.OPEN, DisputeCase.status == DisputeStatus.UNDER_REVIEW, DisputeCase.status == DisputeStatus.WAITING_RESPONSE, DisputeCase.status == DisputeStatus.ESCALATED)
    bq = select(func.coalesce(func.sum(CommissionAgreement.basis_amount), 0)).select_from(CommissionAgreement)
    bq = bq.where(s_comm)
    pq = _payments(agency_id)
    return NetworkOverviewRead(
        agencies_total=await _count(session, Agency, Agency.id == agency_id),
        agencies_verified=await _count(session, Agency, Agency.id == agency_id, Agency.status == AgencyStatus.VERIFIED),
        cooperations_pending=await _count(session, AgencyCooperation, AgencyCooperation.status == CooperationStatus.PENDING, s_coop),
        cooperations_approved=await _count(session, AgencyCooperation, AgencyCooperation.status == CooperationStatus.APPROVED, s_coop),
        shares_active=await _count(session, ListingShare, ListingShare.status == ShareStatus.ACTIVE, s_share),
        shares_total=await _count(session, ListingShare, s_share),
        referrals_open=await _count(session, LeadReferral, open_ref, s_ref),
        referrals_converted=await _count(session, LeadReferral, LeadReferral.stage == ReferralStatus.CONVERTED, s_ref),
        transfers_total=await _count(session, ListingTransferHistory, s_tr),
        commissions_open=await _count(session, CommissionAgreement, open_comm, s_comm),
        commissions_basis_total=int((await session.exec(bq)).one() or 0),
        commissions_paid_total=int((await session.exec(pq)).one() or 0),
        disputes_open=await _count(session, DisputeCase, open_disp, s_disp),
        audit_total=await _count(session, AuditEvent, s_audit),
    )


@router.get("/reports", response_model=NetworkReportsRead)
async def network_reports(
    session: SessionDep,
    _licence: LicenseGuard,
    agency_id: ReportAgencyDep,
) -> NetworkReportsRead:
    s_share = _sided(agency_id, ListingShare.source_agency_id, ListingShare.target_agency_id)
    s_ref = _sided(agency_id, LeadReferral.source_agency_id, LeadReferral.target_agency_id)
    s_tr = _sided(agency_id, ListingTransferHistory.from_agency_id, ListingTransferHistory.to_agency_id)
    s_comm = _sided(agency_id, CommissionAgreement.source_agency_id, CommissionAgreement.target_agency_id)
    s_disp = _sided(agency_id, DisputeCase.claimant_agency_id, DisputeCase.respondent_agency_id)
    s_coop = _sided(agency_id, AgencyCooperation.requester_agency_id, AgencyCooperation.target_agency_id)
    shares = await _group(session, ListingShare, ListingShare.status, s_share)
    referrals = await _group(session, LeadReferral, LeadReferral.stage, s_ref)
    transfers = await _group(session, ListingTransferHistory, ListingTransferHistory.status, s_tr)
    commissions = await _group(session, CommissionAgreement, CommissionAgreement.status, s_comm)
    disputes = await _group(session, DisputeCase, DisputeCase.status, s_disp)
    cooperations = await _group(session, AgencyCooperation, AgencyCooperation.status, s_coop)
    audits = await _group(session, AuditEvent, AuditEvent.action,
                          _sided(agency_id, AuditEvent.actor_agency_id, AuditEvent.target_agency_id))
    bq = select(func.coalesce(func.sum(CommissionAgreement.basis_amount), 0)).select_from(CommissionAgreement)
    bq = bq.where(s_comm)
    total_basis = int((await session.exec(bq)).one() or 0)
    pq = _payments(agency_id)
    total_paid = int((await session.exec(pq)).one() or 0)
    conv_total = sum(r.count for r in referrals)
    conv_done = next((r.count for r in referrals if r.status == "CONVERTED"), 0)
    return NetworkReportsRead(
        shares_by_status=shares, referrals_by_stage=referrals, transfers_by_status=transfers,
        commissions_by_status=commissions, disputes_by_status=disputes,
        cooperations_by_status=cooperations, audit_by_action=audits,
        total_basis=total_basis, total_paid=total_paid,
        total_remaining=max(total_basis - total_paid, 0),
        conversion_rate_pct=round(conv_done * 100 / conv_total) if conv_total else 0,
    )
