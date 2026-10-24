"""Seed sample data for the network menus (idempotent)."""
from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401
from app.core.config import get_settings
from app.models.agency_network import Agency, AgencyCooperation
from app.models.base import utcnow
from app.models.enums import AgencyStatus, CooperationScope, CooperationStatus
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
    AuditAction,
    CommissionModel,
    CommissionStatus,
    DisputeCategory,
    DisputeStatus,
    ListingShareMode,
    ReferralStatus,
    ShareStatus,
    TransferStatus,
)

AGENCIES = [
    {"slug": "tehran-central", "name": "Tehran Central Realty", "name_fa": "املاک مرکز تهران", "city": "تهران", "district": "سعادت‌آباد", "phone": "02122334455", "status": AgencyStatus.VERIFIED, "description": "دفتر مرکزی تهران؛ متخصص آپارتمان‌های شمال شهر."},
    {"slug": "pars-vanak", "name": "Pars Vanak", "name_fa": "املاک پارس ونک", "city": "تهران", "district": "ونک", "phone": "02188776655", "status": AgencyStatus.VERIFIED, "description": "تمرکز روی فایل‌های اداری و تجاری ونک و ملاصدرا."},
    {"slug": "sahil-karaj", "name": "Sahil Karaj", "name_fa": "املاک ساحل کرج", "city": "کرج", "district": "گوهردشت", "phone": "02634455667", "status": AgencyStatus.VERIFIED, "description": "فایل‌های مسکونی کرج و حومه با کارشناسی رایگان."},
    {"slug": "reyhan-shiraz", "name": "Reyhan Shiraz", "name_fa": "املاک ریحان شیراز", "city": "شیراز", "district": "معالی‌آباد", "phone": "07136363636", "status": AgencyStatus.VERIFIED, "description": "ویلاها و آپارتمان‌های معالی‌آباد و قصرالدشت."},
    {"slug": "kaspian-rasht", "name": "Kaspian Rasht", "name_fa": "املاک کاسپین رشت", "city": "رشت", "district": "گلسار", "phone": "01332112233", "status": AgencyStatus.PENDING, "description": "دفتر تازه‌پیوسته؛ در انتظار تأیید شبکه."},
    {"slug": "tabriz-elgoli", "name": "Elgoli Tabriz", "name_fa": "املاک ائل‌گلی تبریز", "city": "تبریز", "district": "ائل‌گلی", "phone": "04133334444", "status": AgencyStatus.VERIFIED, "description": "پوشش شرق تبریز و فایل‌های نوساز."},
]


def _db_url() -> str:
    raw = get_settings().database_url
    if "+psycopg" in raw:
        return raw.replace("+psycopg", "+asyncpg")
    return raw


async def main() -> None:
    engine = create_async_engine(_db_url())
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        existing = (await s.exec(select(Agency))).all()
        by_slug = {a.slug: a for a in existing}
        agencies: list[Agency] = []
        for spec in AGENCIES:
            if spec["slug"] in by_slug:
                agencies.append(by_slug[spec["slug"]])
                continue
            a = Agency(**spec)
            s.add(a)
            agencies.append(a)
        await s.flush()
        a0, a1, a2, a3, a4, a5 = agencies
        now = utcnow()
        coops = [
            AgencyCooperation(requester_agency_id=a0.id, target_agency_id=a1.id, status=CooperationStatus.APPROVED, scope=CooperationScope.SHARE_LISTINGS, granted_scopes="SHARE_LISTINGS,REFER_LEADS", default_commission_pct=50, decided_at=now, requested_by="manager", decided_by="manager"),
            AgencyCooperation(requester_agency_id=a0.id, target_agency_id=a2.id, status=CooperationStatus.APPROVED, scope=CooperationScope.CO_BROKE, granted_scopes="CO_BROKE", default_commission_pct=50, decided_at=now, requested_by="manager", decided_by="manager"),
            AgencyCooperation(requester_agency_id=a3.id, target_agency_id=a0.id, status=CooperationStatus.PENDING, scope=CooperationScope.REFER_LEADS, default_commission_pct=30, requested_by="manager"),
            AgencyCooperation(requester_agency_id=a4.id, target_agency_id=a0.id, status=CooperationStatus.PENDING, scope=CooperationScope.SHARE_LISTINGS, default_commission_pct=50, requested_by="manager"),
            AgencyCooperation(requester_agency_id=a5.id, target_agency_id=a1.id, status=CooperationStatus.REJECTED, scope=CooperationScope.FULL_MERGE, default_commission_pct=50, decided_at=now, decision_reason="ادغام کامل در برنامه نیست", requested_by="manager", decided_by="manager"),
            AgencyCooperation(requester_agency_id=a1.id, target_agency_id=a3.id, status=CooperationStatus.APPROVED, scope=CooperationScope.SHARE_LISTINGS, granted_scopes="SHARE_LISTINGS", default_commission_pct=40, decided_at=now, requested_by="manager", decided_by="manager"),
        ]
        have = {(str(c.requester_agency_id), str(c.target_agency_id), c.status.value) for c in (await s.exec(select(AgencyCooperation))).all()}
        for c in coops:
            key = (str(c.requester_agency_id), str(c.target_agency_id), c.status.value)
            if key not in have:
                s.add(c)
                have.add(key)
        await s.flush()
        p1, p2, p3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        if not (await s.exec(select(ListingShare))).all():
            for sh in [
                ListingShare(property_id=p1, source_agency_id=a0.id, target_agency_id=a1.id, mode=ListingShareMode.SHARE, status=ShareStatus.ACTIVE, target_agent="moshaver_vanak", note="آپارتمان ۱۲۰ متری سعادت‌آباد", created_by="manager"),
                ListingShare(property_id=p2, source_agency_id=a1.id, target_agency_id=a0.id, mode=ListingShareMode.SHARE, status=ShareStatus.ACTIVE, note="دفتر اداری ونک ۸۵ متری", created_by="manager"),
                ListingShare(property_id=p3, source_agency_id=a0.id, target_agency_id=a2.id, mode=ListingShareMode.SHARE, status=ShareStatus.PENDING, note="گوهردشت؛ در انتظار تأیید", created_by="manager"),
                ListingShare(property_id=p1, source_agency_id=a2.id, target_agency_id=a0.id, mode=ListingShareMode.SHARE, status=ShareStatus.REVOKED, revoked_by="manager", note="لغوشده پس از فروش مستقیم", created_by="manager"),
            ]:
                s.add(sh)
            await s.flush()
            for sh in (await s.exec(select(ListingShare))).all():
                s.add(ListingSharePermission(share_id=sh.id, view_summary=True, view_full_details=True, allow_notes=True, allow_visit_request=True, updated_by="manager"))
            await s.flush()
        if not (await s.exec(select(LeadReferral))).all():
            for r in [
                LeadReferral(subject="خریدار آپارتمان ونک", client_masked="خانواده م****", source_agency_id=a0.id, target_agency_id=a1.id, assigned_to="moshaver_vanak", referral_fee_pct=25, stage=ReferralStatus.IN_FOLLOW_UP, note="بودجه تا ۱۲ میلیارد", created_by="manager"),
                LeadReferral(subject="مستأجر اداری ملاصدرا", client_masked="شرکت پ****", source_agency_id=a1.id, target_agency_id=a0.id, assigned_to="moshaver_markaz", referral_fee_pct=20, stage=ReferralStatus.ACCEPTED, created_by="manager"),
                LeadReferral(subject="خریدار ویلا معالی‌آباد", client_masked="آقای ر****", source_agency_id=a0.id, target_agency_id=a3.id, assigned_to="moshaver_reyhan", referral_fee_pct=30, stage=ReferralStatus.CONVERTED, outcome="قولنامه شد", created_by="manager"),
                LeadReferral(subject="سرمایه‌گذار کرج", client_masked="خانم س****", source_agency_id=a2.id, target_agency_id=a0.id, referral_fee_pct=15, stage=ReferralStatus.SENT, created_by="manager"),
                LeadReferral(subject="خریدار ائل‌گلی", client_masked="آقای ت****", source_agency_id=a5.id, target_agency_id=a1.id, referral_fee_pct=20, stage=ReferralStatus.LOST, outcome="منصرف شد", created_by="manager"),
            ]:
                s.add(r)
            await s.flush()
        if not (await s.exec(select(ListingTransferHistory))).all():
            s.add(ListingTransferHistory(property_id=p1, from_agency_id=a0.id, to_agency_id=a1.id, from_user="manager", to_user="moshaver_vanak", status=TransferStatus.COMPLETED, reason="نزدیکی به محل فایل", residual_commission_pct=10, executed_by="manager"))
            s.add(ListingTransferHistory(property_id=p3, from_agency_id=a2.id, to_agency_id=a0.id, from_user="manager", to_user="moshaver_markaz", status=TransferStatus.PENDING, reason="درخواست پوشش تهران", executed_by="manager"))
            await s.flush()
        if not (await s.exec(select(CommissionAgreement))).all():
            c1 = CommissionAgreement(property_id=p1, source_agency_id=a0.id, target_agency_id=a1.id, model=CommissionModel.PERCENTAGE, status=CommissionStatus.LOCKED, basis_amount=120000000000, currency="IRR", note="معامله مشترک سعادت‌آباد", locked_by="manager", created_by="manager")
            c2 = CommissionAgreement(property_id=p2, source_agency_id=a1.id, target_agency_id=a0.id, model=CommissionModel.PERCENTAGE, status=CommissionStatus.PARTIALLY_PAID, basis_amount=85000000000, currency="IRR", note="اجاره اداری ونک", locked_by="manager", created_by="manager")
            c3 = CommissionAgreement(source_agency_id=a0.id, target_agency_id=a3.id, model=CommissionModel.PERCENTAGE, status=CommissionStatus.DRAFT, basis_amount=60000000000, currency="IRR", note="پیش‌نویس شیراز", created_by="manager")
            s.add(c1); s.add(c2); s.add(c3)
            await s.flush()
            al1 = CommissionAllocation(agreement_id=c1.id, agency_id=a0.id, agent="manager_a0", percent=50)
            al2 = CommissionAllocation(agreement_id=c1.id, agency_id=a1.id, agent="moshaver_vanak", percent=50)
            al3 = CommissionAllocation(agreement_id=c2.id, agency_id=a1.id, agent="manager_a1", percent=60)
            al4 = CommissionAllocation(agreement_id=c2.id, agency_id=a0.id, agent="manager_a0", percent=40)
            s.add(al1); s.add(al2); s.add(al3); s.add(al4)
            await s.flush()
            s.add(CommissionPayment(allocation_id=al3.id, amount=20000000000, reference="RES-88121", recorded_by="manager"))
            s.add(CommissionPayment(allocation_id=al4.id, amount=10000000000, reference="RES-88122", recorded_by="manager"))
            await s.flush()
        if not (await s.exec(select(DisputeCase))).all():
            d1 = DisputeCase(category=DisputeCategory.COMMISSION_MISMATCH, status=DisputeStatus.OPEN, claimant_agency_id=a0.id, respondent_agency_id=a1.id, property_id=p1, title="مغایرت سهم کمیسیون سعادت‌آباد", detail="سهم ۵۰٪ ثبت شده ولی ۴۰٪ واریز شد.", opened_by="manager")
            d2 = DisputeCase(category=DisputeCategory.SETTLEMENT_DELAY, status=DisputeStatus.UNDER_REVIEW, claimant_agency_id=a1.id, respondent_agency_id=a0.id, title="تأخیر تسویه اجاره ونک", detail="تسویه مرحله دوم با تأخیر.", opened_by="manager")
            d3 = DisputeCase(category=DisputeCategory.CLIENT_OWNERSHIP, status=DisputeStatus.RESOLVED, claimant_agency_id=a0.id, respondent_agency_id=a3.id, title="ادعای مالکیت مشتری شیراز", detail="هر دو دفتر مدعی معرفی مشتری هستند.", resolution="مالکیت برای دفتر مرکز تهران ثبت شد.", opened_by="manager", resolved_by="admin")
            s.add(d1); s.add(d2); s.add(d3)
            await s.flush()
            s.add(DisputeMessage(dispute_id=d1.id, author="manager_a0", body="لطفاً رسید واریز را بررسی کنید."))
            s.add(DisputeMessage(dispute_id=d1.id, author="manager_a1", body="مابه‌التفاوت تا فردا واریز می‌شود."))
            await s.flush()
        if not (await s.exec(select(AuditEvent))).all():
            for action, actor, aag, etype, pid, tgt, detail in [
                (AuditAction.SHARE_CREATED, "manager_a0", a0.id, "share", p1, a1.id, "mode=SHARE"),
                (AuditAction.SHARE_REVOKED, "manager_a2", a2.id, "share", p1, a0.id, "فروش مستقیم"),
                (AuditAction.TRANSFER_EXECUTED, "manager_a0", a0.id, "transfer", p1, a1.id, "residual=10%"),
                (AuditAction.COMMISSION_LOCKED, "manager_a0", a0.id, "commission", p1, a1.id, "قفل توافق"),
                (AuditAction.PAYMENT_RECORDED, "manager_a1", a1.id, "commission_payment", p2, a0.id, "amount=20000000000"),
                (AuditAction.DISPUTE_OPENED, "manager_a0", a0.id, "dispute", p1, a1.id, "مغایرت سهم"),
                (AuditAction.DISPUTE_RESOLVED, "admin", None, "dispute", None, a3.id, "مالکیت مشتری"),
                (AuditAction.PERMISSION_CHANGED, "manager_a0", a0.id, "share", p1, a1.id, "visit_request=true"),
                (AuditAction.LISTING_EXPORTED, "moshaver_vanak", a1.id, "share", p2, a0.id, "خروجی PDF"),
                (AuditAction.OWNER_PHONE_REVEALED, "moshaver_markaz", a0.id, "share", p2, a1.id, "افشای شماره مالک"),
            ]:
                s.add(AuditEvent(action=action, actor=actor, actor_agency_id=aag, entity_type=etype, property_id=pid, target_agency_id=tgt, detail=detail))
            await s.flush()
        await s.commit()
        print("seed-network part2 done")


if __name__ == "__main__":
    asyncio.run(main())
