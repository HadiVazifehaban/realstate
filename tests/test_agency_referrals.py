"""Referral policy primitives use actual office/payment records only."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.models.agency_network import Agency, AgencyMembership
from app.models.billing import AgencyReferral, PaymentOrder, ReferralCredit
from app.models.enums import (
    AgencyReferralStatus,
    AgencyStatus,
    PaymentEnvironmentMode,
    PaymentOrderStatus,
    ReferralCreditStatus,
)
from app.services import agency_referrals


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    from conftest import create_sqlite_schema

    await create_sqlite_schema(engine, "agency_membership", "agency_referral", "referral_credit", "payment_order", "financial_audit_log")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


def _agency(name: str, code: str) -> Agency:
    return Agency(slug=name, name=name, referral_code=code, status=AgencyStatus.PENDING)


@pytest.mark.asyncio
async def test_records_optional_referral_and_rejects_self_referral(session):
    referrer = _agency("referrer", "SHREFERRER1")
    referred = _agency("referred", "SHREFERRED1")
    session.add_all([referrer, referred])
    await session.flush()
    session.add(AgencyMembership(
        agency_id=referrer.id, user_subject="founder", role="FOUNDER", created_by_subject="founder"
    ))
    await session.flush()

    with pytest.raises(ValueError, match="عضو فعال"):
        await agency_referrals.record_agency_referral(
            session, referred_agency_id=referred.id, referral_code=referrer.referral_code,
            source="workspace_registration", actor_subject="founder",
        )

    row = await agency_referrals.record_agency_referral(
        session, referred_agency_id=referred.id, referral_code="", source="workspace_registration",
        actor_subject="another-founder",
    )
    assert row is None


@pytest.mark.asyncio
async def test_only_first_real_approved_order_completes_and_issues_one_credit(session):
    referrer = _agency("referrer", "SHREFERRER2")
    referred = _agency("referred", "SHREFERRED2")
    session.add_all([referrer, referred])
    await session.flush()
    referral = AgencyReferral(
        referrer_agency_id=referrer.id, referred_agency_id=referred.id,
        code_used=referrer.referral_code, status=AgencyReferralStatus.PENDING,
    )
    test_order = PaymentOrder(
        order_number="TEST-REF", agency_id=str(referred.id), user_id="u", plan="monthly",
        amount_toman=499000, card_number_snapshot_encrypted="x", card_last4="0000",
        card_holder_snapshot="", card_configured_snapshot=False, is_test=True,
        environment_mode=PaymentEnvironmentMode.TEST, status=PaymentOrderStatus.TEST_APPROVED_NO_ACTIVATION,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    live_order = PaymentOrder(
        order_number="LIVE-REF", agency_id=str(referred.id), user_id="u", plan="monthly",
        amount_toman=499000, card_number_snapshot_encrypted="x", card_last4="3456",
        card_holder_snapshot="", card_configured_snapshot=True, is_test=False,
        environment_mode=PaymentEnvironmentMode.LIVE, status=PaymentOrderStatus.APPROVED,
        approved_at=datetime.now(timezone.utc), activated_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    session.add_all([referral, test_order, live_order])
    await session.flush()

    assert not await agency_referrals.complete_first_paid_referral(
        session, referred_agency_id=str(referred.id), order_id=test_order.id
    )
    assert await agency_referrals.complete_first_paid_referral(
        session, referred_agency_id=str(referred.id), order_id=live_order.id
    )
    assert not await agency_referrals.complete_first_paid_referral(
        session, referred_agency_id=str(referred.id), order_id=live_order.id
    )
    credits = (await session.exec(select(ReferralCredit))).all()
    assert len(credits) == 1
    assert credits[0].status == ReferralCreditStatus.PENDING


@pytest.mark.asyncio
async def test_reservation_preview_excludes_reserved_credits(session):
    office = _agency("credit-office", "SHCREDIT001")
    other = _agency("other-office", "SHOTHER0001")
    session.add_all([office, other])
    await session.flush()
    order_id = uuid.uuid4()
    referral = AgencyReferral(
        referrer_agency_id=office.id, referred_agency_id=other.id,
        code_used=office.referral_code, status=AgencyReferralStatus.COMPLETED,
    )
    session.add(referral)
    await session.flush()
    session.add(ReferralCredit(
        agency_id=office.id, referral_id=referral.id, percent=5,
        status=ReferralCreditStatus.AVAILABLE,
    ))
    await session.flush()

    assert await agency_referrals.reserve_credits_for_order(
        session, agency_id=str(office.id), order_id=order_id
    ) == (5, 1)
    assert await agency_referrals.preview_credits(session, agency_id=str(office.id)) == (0, 0)
