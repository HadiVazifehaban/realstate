#!/usr/bin/env python3
"""Idempotently seed the Phase 1.5 fixture in a disposable test realm/database.

This script never uses the process' operational DATABASE_URL or Keycloak
settings. It requires explicit test-only URLs and a confirmation marker.
It creates no passwords or sends OTP/SMS.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401
from app.core.config import NodeMode, Settings
from app.models.agency_network import Agency, AgencyMembership
from app.models.agency_user import AgencyUser
from app.models.billing import AgencySubscription, SubscriptionPlan
from app.models.enums import AgencyStatus, PropertySource, PropertyStatus, UserRole
from app.models.property import Property
from app.services import billing, keycloak_admin


BATCH = "phase15-20261028"
PREFIX = f"{BATCH}-"
AGENCY_PREFIX = f"{BATCH}-office-"

USER_SPECS = (
    *(('user', f'user{i:02d}', UserRole.USER, 'ROLE_VERIFIED_USER') for i in range(1, 4)),
    *(('unverified', f'unverified{i:02d}', UserRole.GUEST, 'ROLE_UNVERIFIED_USER') for i in range(1, 3)),
    *(('owner', f'owner{i:02d}', UserRole.OWNER, 'ROLE_OWNER') for i in range(1, 5)),
    *(('junior', f'junior{i:02d}', UserRole.AGENT, 'ROLE_JUNIOR_BROKER') for i in range(1, 5)),
    *(('senior', f'senior{i:02d}', UserRole.AGENT, 'ROLE_SENIOR_BROKER') for i in range(1, 5)),
    *(('manager', f'manager{i:02d}', UserRole.OFFICE_MANAGER, 'ROLE_AGENCY_MANAGER') for i in range(1, 5)),
    *(('analyst', f'analyst{i:02d}', UserRole.GUEST, 'ROLE_DATA_ANALYST') for i in range(1, 3)),
    ('supervisor', 'supervisor01', UserRole.SUPERVISOR, 'ROLE_SUPERVISOR'),
    ('admin', 'admin01', UserRole.ADMIN, 'ROLE_ADMIN'),
)


def _settings() -> Settings:
    if os.getenv("PHASE15_TEST_SEED_CONFIRM") != "YES":
        raise SystemExit("Set PHASE15_TEST_SEED_CONFIRM=YES for the disposable fixture only.")
    database_url = os.getenv("PHASE15_TEST_DATABASE_URL", "")
    issuer = os.getenv("PHASE15_TEST_KEYCLOAK_ISSUER", "")
    client_id = os.getenv("PHASE15_TEST_KEYCLOAK_CLIENT_ID", "")
    client_secret = os.getenv("PHASE15_TEST_KEYCLOAK_CLIENT_SECRET", "")
    realm = os.getenv("PHASE15_TEST_KEYCLOAK_REALM", "")
    if not all((database_url, issuer, client_id, client_secret, realm)):
        raise SystemExit("All PHASE15_TEST_* database and Keycloak settings are required.")
    if "phase15" not in database_url or "phase15" not in issuer.lower():
        raise SystemExit("Refusing URLs that do not identify the Phase 1.5 test environment.")
    return Settings(
        node_mode=NodeMode.LOCAL,
        database_url=database_url,
        keycloak_issuer=issuer,
        keycloak_realm=realm,
        keycloak_admin_client_id=client_id,
        keycloak_admin_client_secret=client_secret,
    )


def _async_url(value: str) -> str:
    return value.replace("+psycopg", "+asyncpg")


async def _ensure_plans(session: AsyncSession) -> None:
    for plan in billing.PLANS.values():
        row = await session.get(SubscriptionPlan, plan.id)
        if row is None:
            session.add(SubscriptionPlan(
                id=plan.id, title=plan.title, description=plan.description,
                price_toman=plan.price_toman, duration_days=plan.duration_days,
                listing_quota=plan.listing_quota, sms_quota=plan.sms_quota,
                regions_quota=plan.regions_quota, advisor_quota=plan.advisor_quota,
                is_unlimited=plan.is_unlimited, features=list(plan.features),
                sort_order=plan.sort_order,
            ))


async def main() -> None:
    settings = _settings()
    engine = create_async_engine(_async_url(settings.database_url))
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    try:
        directory = {
            user.email.casefold(): user
            for user in await keycloak_admin.list_directory_users(settings)
            if user.email.casefold().startswith(PREFIX)
        }
        subjects: dict[str, str] = {}
        for _kind, slug, role, realm_role in USER_SPECS:
            email = f"{PREFIX}{slug}@example.test"
            user = directory.get(email.casefold())
            if user is None:
                user = await keycloak_admin.create_user(
                    settings, email=email, first_name="Phase15", last_name=slug,
                    phone="", role=role,
                    realm_role=realm_role if role is UserRole.AGENT else None,
                    enabled=True,
                )
                if role is not UserRole.AGENT:
                    await keycloak_admin._set_realm_roles(settings, user.id, [realm_role])
            subjects[slug] = user.id

        async with maker() as session:
            await _ensure_plans(session)
            agencies: dict[str, Agency] = {}
            for code, plan, status, days in (
                ("bronze", "monthly", "active", 30),
                ("silver", "quarterly", "active", 90),
                ("gold", "yearly", "active", 365),
                ("expired", "monthly", "active", -30),
                ("pending", "monthly", "pending_payment", 30),
            ):
                slug = f"{AGENCY_PREFIX}{code}"
                agency = (await session.exec(select(Agency).where(Agency.slug == slug))).first()
                if agency is None:
                    agency = Agency(slug=slug, name=f"Phase 1.5 {code}", name_fa=f"دفتر تست {code}",
                                    city="تهران", status=AgencyStatus.VERIFIED,
                                    referral_code=f"P15{code[:5].upper()}")
                    session.add(agency)
                    await session.flush()
                agencies[code] = agency
                starts = now - timedelta(days=2 if days > 0 else 60)
                ends = now + timedelta(days=days) if days > 0 else now - timedelta(days=1)
                existing = (await session.exec(select(AgencySubscription).where(
                    AgencySubscription.agency_id == str(agency.id),
                    AgencySubscription.plan == plan,
                ))).first()
                if existing is None:
                    catalog = billing.PLANS[plan]
                    session.add(AgencySubscription(
                        agency_id=str(agency.id), plan=plan, status=status,
                        starts_at=starts, expires_at=ends,
                        listing_quota=catalog.listing_quota, sms_quota=catalog.sms_quota,
                        regions_quota=catalog.regions_quota, advisor_quota=catalog.advisor_quota,
                        is_unlimited=catalog.is_unlimited,
                    ))

            membership_map = {
                "bronze": ("manager01", "junior01", "junior02"),
                "silver": ("manager02", "junior03", "senior01", "senior02"),
                "gold": ("manager03", "manager04", "senior03", "senior04"),
                "expired": ("junior04",),
                "pending": (),
            }
            for code, users in membership_map.items():
                for slug in users:
                    exists = (await session.exec(select(AgencyMembership).where(
                        AgencyMembership.agency_id == agencies[code].id,
                        AgencyMembership.user_subject == subjects[slug],
                    ))).first()
                    if exists is None:
                        session.add(AgencyMembership(
                            agency_id=agencies[code].id, user_subject=subjects[slug],
                            role=("OFFICE_MANAGER" if slug.startswith("manager") else
                                  "SENIOR_BROKER" if slug.startswith("senior") else "JUNIOR_BROKER"),
                            created_by_subject=subjects["admin01"],
                        ))

            for kind, slug, role, _realm_role in USER_SPECS:
                if role not in {UserRole.AGENT, UserRole.OFFICE_MANAGER, UserRole.SUPERVISOR, UserRole.ADMIN}:
                    continue
                exists = (await session.exec(select(AgencyUser).where(
                    AgencyUser.username == slug,
                ))).first()
                if exists is None:
                    session.add(AgencyUser(username=slug, full_name=f"Phase15 {slug}", role=role))

            owners = [subjects[f"owner{i:02d}"] for i in range(1, 5)]
            scenarios = (
                ("active-bronze", PropertyStatus.ACTIVE, agencies["bronze"].id, subjects["junior01"], PropertySource.MANUAL_OFFICE),
                ("draft-bronze", PropertyStatus.DRAFT, agencies["bronze"].id, subjects["junior01"], PropertySource.MANUAL_OFFICE),
                ("withdrawn-silver", PropertyStatus.WITHDRAWN, agencies["silver"].id, subjects["senior01"], PropertySource.MANUAL_OFFICE),
                ("active-gold", PropertyStatus.ACTIVE, agencies["gold"].id, subjects["senior03"], PropertySource.MANUAL_OFFICE),
                ("personal-owner", PropertyStatus.ACTIVE, None, owners[0], PropertySource.INTERNAL_USER),
                ("scraped", PropertyStatus.ACTIVE, None, None, PropertySource.DIVAR),
            )
            for code, status, agency_id, owner_subject, source in scenarios:
                ref = f"{BATCH}:{code}"
                existing = (await session.exec(select(Property).where(Property.source_ref == ref))).first()
                if existing is None:
                    session.add(Property(
                        code=ref, source_ref=ref, title=f"Phase 1.5 {code}",
                        status=status, agency_id=agency_id, owner_subject=owner_subject,
                        source=source, city="تهران", neighborhood="آزمایشی",
                        latitude=35.72, longitude=51.40, area=100, rooms=2,
                        total_price=10_000_000_000, price_per_meter=100_000_000,
                    ))
            await session.commit()
        print(f"Phase 1.5 fixture ready: users={len(USER_SPECS)}, offices=5, plans=4, properties=6, batch={BATCH}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
