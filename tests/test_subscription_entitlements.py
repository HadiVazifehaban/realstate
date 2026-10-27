from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.agency_network import Agency
from app.models.agency_user import AgencyUser
from app.models.billing import AgencySubscription, SubscriptionPlan
from app.models.enums import AgencyStatus, SubmitterType
from app.models.property import Property
from app.services import billing
from app.services.entitlements import EntitlementLimitExceeded, enforce_listing_quota, get_listing_quota
from tests.conftest import create_sqlite_schema


@pytest.mark.asyncio
async def test_active_office_listing_quota_counts_only_scoped_first_party_inventory() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_sqlite_schema(engine, "subscription_plan", "agency", "agency_user", "agency_subscription", "property")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    office_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    async with factory() as session:
        free = billing.PLANS["free"]
        session.add(SubscriptionPlan(
            id=free.id, title=free.title, description=free.description, price_toman=free.price_toman,
            duration_days=free.duration_days, listing_quota=free.listing_quota,
            sms_quota=free.sms_quota, regions_quota=free.regions_quota,
            advisor_quota=free.advisor_quota, is_unlimited=free.is_unlimited,
            features=list(free.features), is_active=True, sort_order=0,
        ))
        session.add(Agency(
            id=office_id, slug="quota-test-office", name="Quota Test", name_fa="دفتر آزمون",
            referral_code="QTEST123", status=AgencyStatus.VERIFIED,
        ))
        session.add(AgencyUser(id=actor_id, username="quota-test", agency_id=str(office_id)))
        session.add(AgencySubscription(
            agency_id=str(office_id), plan="monthly", status="active",
            starts_at=now - timedelta(days=2), expires_at=now + timedelta(days=28),
            listing_quota=2, sms_quota=30, regions_quota=1, advisor_quota=3,
            is_unlimited=False,
        ))
        session.add_all([
            Property(title=f"office-{index}", agency_id=office_id, created_by_id=actor_id,
                     submitter_type=SubmitterType.AGENCY, created_at=now - timedelta(days=1))
            for index in range(2)
        ])
        # Scraped rows are global and must not consume an office's subscription.
        session.add(Property(title="scraped", agency_id=None, submitter_type=None, created_at=now))
        await session.commit()

        quota = await get_listing_quota(
            session, agency_key=str(office_id), agency_uuid=office_id,
            actor_user_id=actor_id, now=now,
        )
        assert quota.used == 2
        assert quota.limit == 2
        assert quota.remaining == 0
        with pytest.raises(EntitlementLimitExceeded):
            await enforce_listing_quota(
                session, agency_key=str(office_id), agency_uuid=office_id,
                actor_user_id=actor_id, now=now,
            )

        subscription = (await session.exec(select(AgencySubscription))).first()
        subscription.is_unlimited = True
        subscription.listing_quota = None
        session.add(subscription)
        await session.commit()
        unlimited = await get_listing_quota(
            session, agency_key=str(office_id), agency_uuid=office_id,
            actor_user_id=actor_id, now=now,
        )
        assert unlimited.unlimited is True
        assert unlimited.limit is None
        assert unlimited.remaining is None

    await engine.dispose()
