"""Server-side policy and operations for agency referral rewards.

The current billing product is manual card-to-card review, not an automated
gateway. This module therefore completes referrals only from the existing
real-order approval transition and does not pretend a receipt is a payment.
"""

from __future__ import annotations

import secrets
import string
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.agency_network import Agency, AgencyMembership
from app.models.billing import AgencyReferral, FinancialAuditLog, ReferralCredit
from app.models.enums import AgencyReferralStatus, ReferralCreditStatus
from app.models.base import utcnow


@dataclass(frozen=True)
class ReferralPolicy:
    credit_percent: int = 5
    invoice_cap_percent: int = 20
    required_successful_paid_orders: int = 1
    allow_stacking_with_other_discounts: bool = False


REFERRAL_POLICY = ReferralPolicy()
_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 10
_CODE_ATTEMPTS = 12


def normalize_referral_code(value: str) -> str:
    return "".join((value or "").split()).upper()


def new_referral_code() -> str:
    return "SH" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


async def ensure_agency_referral_code(session: AsyncSession, agency: Agency) -> str:
    """Assign a stable, cryptographically random code, retrying unique races."""
    if agency.referral_code:
        return agency.referral_code
    for _ in range(_CODE_ATTEMPTS):
        try:
            await session.execute(
                select(Agency.id).where(Agency.id == agency.id).with_for_update()
            )
            current = await session.get(Agency, agency.id)
            if current is None:
                raise RuntimeError("Agency disappeared while assigning referral code")
            if current.referral_code:
                agency.referral_code = current.referral_code
                return current.referral_code
            current.referral_code = new_referral_code()
            session.add(current)
            await session.flush()
            agency.referral_code = current.referral_code
            return current.referral_code
        except IntegrityError:
            await session.rollback()
            # The conflicting generated code was rolled back; retry under the
            # agency row lock, leaving its other fields unchanged.
    raise RuntimeError("Could not allocate a unique agency referral code")


async def find_referrer(session: AsyncSession, referral_code: str) -> Agency | None:
    code = normalize_referral_code(referral_code)
    if not code:
        return None
    referrer = (await session.exec(
        select(Agency).where(Agency.referral_code == code)
    )).first()
    if referrer is None:
        raise ValueError("کد معرف معتبر نیست.")
    if referrer.status.value == "SUSPENDED":
        raise ValueError("کد معرف معتبر یا فعال نیست.")
    return referrer


async def record_agency_referral(
    session: AsyncSession,
    *,
    referred_agency_id: uuid.UUID,
    referral_code: str,
    source: str,
    actor_subject: str,
) -> AgencyReferral | None:
    """Attach an optional referrer once; an empty code means no referral."""
    code = normalize_referral_code(referral_code)
    if not code:
        return None
    referrer = await find_referrer(session, code)
    assert referrer is not None
    # Serialize creation for the same owner so concurrently submitted requests
    # cannot bypass the self-referral membership check before either commits.
    await session.execute(select(Agency.id).where(Agency.id == referrer.id).with_for_update())
    if referrer.id == referred_agency_id:
        raise ValueError("کد معرف نمی‌تواند متعلق به دفتر خودتان باشد.")

    existing = (await session.exec(
        select(AgencyReferral)
        .where(AgencyReferral.referred_agency_id == referred_agency_id)
        .with_for_update()
    )).first()
    if existing is not None:
        raise ValueError("برای این دفتر قبلاً کد معرف ثبت شده و قابل تغییر نیست.")

    # The creating subject is inserted as the referred office's founder in the
    # same transaction. A code owned by an office they already belong to is a
    # self-referral and must be rejected.
    referrer_member = (await session.exec(
        select(AgencyMembership.id)
        .where(
            AgencyMembership.agency_id == referrer.id,
            AgencyMembership.user_subject == actor_subject,
            AgencyMembership.revoked_at.is_(None),
        )
    )).first()
    if referrer_member is not None:
        raise ValueError("نمی‌توانید دفتری را که عضو فعال آن هستید به‌عنوان معرف انتخاب کنید.")

    row = AgencyReferral(
        referrer_agency_id=referrer.id,
        referred_agency_id=referred_agency_id,
        code_used=code,
        status=AgencyReferralStatus.PENDING,
        source=source[:32],
        created_by_subject=actor_subject[:255],
    )
    session.add(row)
    await session.flush()
    return row


async def complete_first_paid_referral(
    session: AsyncSession,
    *,
    referred_agency_id: str,
    order_id: uuid.UUID,
    now: datetime | None = None,
) -> bool:
    """Idempotently complete one referral and issue exactly one credit."""
    try:
        referred_uuid = uuid.UUID(referred_agency_id)
    except (ValueError, TypeError):
        # Existing deployments can have opaque legacy tenant handles. Those
        # cannot be safely joined to the UUID agency registry.
        return False
    referral = (await session.exec(
        select(AgencyReferral)
        .where(AgencyReferral.referred_agency_id == referred_uuid)
        .with_for_update()
    )).first()
    if referral is None or referral.status is not AgencyReferralStatus.PENDING:
        return False
    from app.models.billing import PaymentOrder
    from app.models.enums import PaymentOrderStatus
    first_paid = (await session.exec(
        select(PaymentOrder).where(
            PaymentOrder.agency_id == referred_agency_id,
            PaymentOrder.plan != "free",
            PaymentOrder.is_test.is_(False),
            PaymentOrder.status == PaymentOrderStatus.APPROVED,
            PaymentOrder.activated_at.is_not(None),
        ).order_by(PaymentOrder.approved_at, PaymentOrder.id).limit(1)
    )).first()
    if first_paid is None or first_paid.id != order_id:
        return False
    existing_credit = (await session.exec(
        select(ReferralCredit).where(ReferralCredit.referral_id == referral.id)
    )).first()
    if existing_credit is not None:
        return False
    now = now or utcnow()
    referral.status = AgencyReferralStatus.COMPLETED
    referral.completed_at = now
    referral.completion_order_id = order_id
    referral.updated_at = now
    session.add(referral)

    session.add(ReferralCredit(
        agency_id=referral.referrer_agency_id,
        referral_id=referral.id,
        status=ReferralCreditStatus.PENDING,
        percent=REFERRAL_POLICY.credit_percent,
        created_at=now,
    ))
    session.add(FinancialAuditLog(
        actor_user_id="system:billing",
        actor_role="system",
        action="referral_completed",
        entity_type="agency_referral",
        entity_id=referral.id,
        before_data={"status": AgencyReferralStatus.PENDING.value},
        after_data={"status": AgencyReferralStatus.COMPLETED.value, "completion_order_id": str(order_id)},
    ))
    await session.flush()
    return True


async def reserve_credits_for_order(
    session: AsyncSession, *, agency_id: str, order_id: uuid.UUID
) -> tuple[int, int]:
    """Atomically reserve up to four credits; returns percent and count."""
    try:
        agency_uuid = uuid.UUID(agency_id)
    except (ValueError, TypeError):
        return 0, 0
    # A lock on the agency row serializes simultaneous order creation even if
    # there are currently no AVAILABLE credits to lock.
    await session.execute(select(Agency.id).where(Agency.id == agency_uuid).with_for_update())
    credits = (await session.exec(
        select(ReferralCredit)
        .where(
            ReferralCredit.agency_id == agency_uuid,
            ReferralCredit.status == ReferralCreditStatus.AVAILABLE,
        )
        .order_by(ReferralCredit.created_at, ReferralCredit.id)
        .limit(REFERRAL_POLICY.invoice_cap_percent // REFERRAL_POLICY.credit_percent)
        .with_for_update()
    )).all()
    for credit in credits:
        credit.status = ReferralCreditStatus.RESERVED
        credit.reserved_order_id = order_id
        session.add(credit)
    return sum(credit.percent for credit in credits), len(credits)


async def preview_credits(session: AsyncSession, *, agency_id: str) -> tuple[int, int]:
    try:
        agency_uuid = uuid.UUID(agency_id)
    except (ValueError, TypeError):
        return 0, 0
    rows = (await session.exec(select(ReferralCredit).where(
        ReferralCredit.agency_id == agency_uuid,
        ReferralCredit.status == ReferralCreditStatus.AVAILABLE,
    ).order_by(ReferralCredit.created_at, ReferralCredit.id).limit(
        REFERRAL_POLICY.invoice_cap_percent // REFERRAL_POLICY.credit_percent
    ))).all()
    return sum(row.percent for row in rows), len(rows)


async def settle_order_credits(
    session: AsyncSession, *, order_id: uuid.UUID, successful: bool
) -> None:
    credits = (await session.exec(
        select(ReferralCredit).where(
            ReferralCredit.reserved_order_id == order_id,
            ReferralCredit.status == ReferralCreditStatus.RESERVED,
        ).with_for_update()
    )).all()
    for credit in credits:
        credit.status = ReferralCreditStatus.CONSUMED if successful else ReferralCreditStatus.AVAILABLE
        if successful:
            credit.consumed_order_id = order_id
        credit.reserved_order_id = None
        credit.updated_at = utcnow()
        session.add(credit)


async def release_expired_reservations(session: AsyncSession, *, now: datetime | None = None) -> int:
    """Release credits held by expired/cancelled/rejected payment orders."""
    from app.models.billing import PaymentOrder
    from app.models.enums import PaymentOrderStatus

    now = now or utcnow()
    credits = (await session.exec(
        select(ReferralCredit)
        .join(PaymentOrder, PaymentOrder.id == ReferralCredit.reserved_order_id)
        .where(
            ReferralCredit.status == ReferralCreditStatus.RESERVED,
            or_(
                (PaymentOrder.expires_at <= now)
                & PaymentOrder.status.in_([
                    PaymentOrderStatus.CREATED,
                    PaymentOrderStatus.PENDING_PAYMENT,
                    PaymentOrderStatus.AWAITING_TRANSFER,
                    PaymentOrderStatus.RECEIPT_SUBMITTED,
                    PaymentOrderStatus.UNDER_REVIEW,
                ]),
                PaymentOrder.status.in_([
                    PaymentOrderStatus.EXPIRED,
                    PaymentOrderStatus.CANCELLED,
                    PaymentOrderStatus.REJECTED,
                    PaymentOrderStatus.TEST_APPROVED_NO_ACTIVATION,
                ]),
            ),
        )
        .with_for_update()
    )).all()
    for credit in credits:
        credit.status = ReferralCreditStatus.AVAILABLE
        credit.reserved_order_id = None
        credit.updated_at = now
        session.add(credit)
    return len(credits)


async def activate_pending_credits(session: AsyncSession, agency_id: uuid.UUID) -> None:
    pending = (await session.exec(
        select(ReferralCredit).where(
            ReferralCredit.agency_id == agency_id,
            ReferralCredit.status == ReferralCreditStatus.PENDING,
        ).where(
            ReferralCredit.referral_id.in_(
                select(AgencyReferral.id).where(
                    AgencyReferral.referrer_agency_id == agency_id,
                    AgencyReferral.status == AgencyReferralStatus.COMPLETED,
                )
            )
        ).with_for_update()
    )).all()
    for credit in pending:
        credit.status = ReferralCreditStatus.AVAILABLE
        credit.updated_at = utcnow()
        session.add(credit)


async def referral_dashboard_data(session: AsyncSession, agency_id: uuid.UUID) -> dict:
    agency = await session.get(Agency, agency_id)
    if agency is None:
        raise ValueError("دفتر پیدا نشد.")
    await ensure_agency_referral_code(session, agency)
    if agency.referral_code:
        await session.commit()
    referrals = (await session.exec(
        select(AgencyReferral).where(AgencyReferral.referrer_agency_id == agency_id)
        .order_by(AgencyReferral.created_at.desc())
    )).all()
    credits = (await session.exec(
        select(ReferralCredit).where(ReferralCredit.agency_id == agency_id)
    )).all()
    available = sum(c.percent for c in credits if c.status is ReferralCreditStatus.AVAILABLE)
    return {
        "referral_code": agency.referral_code,
        "pending_referrals": sum(r.status is AgencyReferralStatus.PENDING for r in referrals),
        "completed_referrals": sum(r.status is AgencyReferralStatus.COMPLETED for r in referrals),
        "credits": {
            state.value.lower(): sum(c.percent for c in credits if c.status is state)
            for state in ReferralCreditStatus
        },
        "next_renewal_percent": min(available, REFERRAL_POLICY.invoice_cap_percent),
        "policy": {
            "credit_percent": REFERRAL_POLICY.credit_percent,
            "invoice_cap_percent": REFERRAL_POLICY.invoice_cap_percent,
            "allow_stacking_with_other_discounts": REFERRAL_POLICY.allow_stacking_with_other_discounts,
        },
        "referrals": [
            {
                "status": row.status.value,
                "created_at": row.created_at.isoformat(),
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            }
            for row in referrals
        ],
    }
