#!/usr/bin/env python3
"""Create twenty clearly-labelled local Keycloak/RBAC demo users.

The script is intentionally local-only and idempotent. It creates no passwords:
demo identities must use Keycloak's normal password-reset flow before login.

Run only with ``DEMO_RBAC_SEED_CONFIRM=YES`` and ``NODE_MODE=LOCAL``.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401
from app.core.config import get_settings
from app.models.agency_network import Agency, AgencyMembership
from app.models.enums import AgencyStatus, UserRole
from app.services import keycloak_admin
from app.services.agency_referrals import ensure_agency_referral_code


DEMO_PREFIX = "demo-rbac-"
OFFICE_SLUG = "demo-rbac-office"

# The first role is the internal role used by provisioning; the second is the
# exact Realm role the UI/admin panel should display.
SEEDS: tuple[tuple[str, str, UserRole, str | None, str | None], ...] = (
    ("unverified", "کاربر تأییدنشده", UserRole.GUEST, "ROLE_UNVERIFIED_USER", None),
    ("unverified2", "کاربر تأییدنشده دوم", UserRole.GUEST, "ROLE_UNVERIFIED_USER", None),
    ("user01", "کاربر تأییدشده یک", UserRole.USER, "ROLE_VERIFIED_USER", None),
    ("user02", "کاربر تأییدشده دو", UserRole.USER, "ROLE_VERIFIED_USER", None),
    ("user03", "کاربر تأییدشده سه", UserRole.USER, "ROLE_VERIFIED_USER", None),
    ("owner01", "مالک آزمایشی یک", UserRole.OWNER, "ROLE_OWNER", None),
    ("owner02", "مالک آزمایشی دو", UserRole.OWNER, "ROLE_OWNER", None),
    ("owner03", "مالک آزمایشی سه", UserRole.OWNER, "ROLE_OWNER", None),
    ("junior01", "مشاور جونیور یک", UserRole.AGENT, "ROLE_JUNIOR_BROKER", "JUNIOR_BROKER"),
    ("junior02", "مشاور جونیور دو", UserRole.AGENT, "ROLE_JUNIOR_BROKER", "JUNIOR_BROKER"),
    ("junior03", "مشاور جونیور سه", UserRole.AGENT, "ROLE_JUNIOR_BROKER", "JUNIOR_BROKER"),
    ("junior04", "مشاور جونیور چهار", UserRole.AGENT, "ROLE_JUNIOR_BROKER", "JUNIOR_BROKER"),
    ("senior01", "مشاور ارشد یک", UserRole.AGENT, "ROLE_SENIOR_BROKER", "SENIOR_BROKER"),
    ("senior02", "مشاور ارشد دو", UserRole.AGENT, "ROLE_SENIOR_BROKER", "SENIOR_BROKER"),
    ("senior03", "مشاور ارشد سه", UserRole.AGENT, "ROLE_SENIOR_BROKER", "SENIOR_BROKER"),
    ("manager01", "مدیر دفتر آزمایشی یک", UserRole.OFFICE_MANAGER, "ROLE_AGENCY_MANAGER", "OFFICE_MANAGER"),
    ("manager02", "مدیر دفتر آزمایشی دو", UserRole.OFFICE_MANAGER, "ROLE_AGENCY_MANAGER", "OFFICE_MANAGER"),
    ("supervisor", "ناظر آزمایشی", UserRole.SUPERVISOR, "ROLE_SUPERVISOR", None),
    ("analyst", "تحلیلگر آزمایشی", UserRole.GUEST, "ROLE_DATA_ANALYST", None),
    ("admin", "مدیر سامانه آزمایشی", UserRole.ADMIN, "ROLE_ADMIN", None),
)


def _async_url(value: str) -> str:
    return value.replace("+psycopg", "+asyncpg") if "+psycopg" in value else value


async def main() -> None:
    settings = get_settings()
    if os.getenv("DEMO_RBAC_SEED_CONFIRM") != "YES":
        raise SystemExit("Set DEMO_RBAC_SEED_CONFIRM=YES to create demo identities.")
    if settings.node_mode.value != "LOCAL":
        raise SystemExit("Refusing to create demo identities outside NODE_MODE=LOCAL.")
    if not keycloak_admin.is_directory_enabled(settings):
        raise SystemExit("Keycloak directory integration is disabled in this environment.")

    engine = create_async_engine(_async_url(settings.database_url))
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        existing = {
            user.email.casefold(): user
            for user in await keycloak_admin.list_directory_users(settings)
            if user.email.casefold().startswith(f"{DEMO_PREFIX}")
        }
        async with maker() as session:
            office = (await session.exec(select(Agency).where(Agency.slug == OFFICE_SLUG))).first()
            if office is None:
                office = Agency(
                    slug=OFFICE_SLUG,
                    name="Demo RBAC Office",
                    name_fa="دفتر آزمایشی نقش‌ها",
                    city="تهران",
                    district="آزمایشی",
                    description="دفتر آزمایشی برای بررسی RBAC و جداسازی دسترسی‌ها.",
                    status=AgencyStatus.VERIFIED,
                )
                session.add(office)
                await session.flush()
                await ensure_agency_referral_code(session, office)

            created = 0
            membership_count = 0
            for slug, display_name, internal_role, realm_role, membership_role in SEEDS:
                email = f"{DEMO_PREFIX}{slug}@example.invalid"
                user = existing.get(email.casefold())
                if user is None:
                    user = await keycloak_admin.create_user(
                        settings,
                        email=email,
                        first_name="Demo",
                        last_name=display_name,
                        phone="",
                        role=internal_role,
                        realm_role=realm_role if realm_role in {"ROLE_JUNIOR_BROKER", "ROLE_SENIOR_BROKER"} else None,
                        enabled=True,
                    )
                    # create_user supports office broker roles directly. The
                    # remaining explicit Realm roles are assigned separately.
                    if realm_role not in {"ROLE_JUNIOR_BROKER", "ROLE_SENIOR_BROKER"}:
                        await keycloak_admin._set_realm_roles(settings, user.id, [realm_role])
                    created += 1

                if membership_role is not None:
                    membership = (await session.exec(select(AgencyMembership).where(
                        AgencyMembership.agency_id == office.id,
                        AgencyMembership.user_subject == user.id,
                    ))).first()
                    if membership is None:
                        session.add(AgencyMembership(
                            agency_id=office.id,
                            user_subject=user.id,
                            role=membership_role,
                            created_by_subject="demo-rbac-seed",
                        ))
                        membership_count += 1

            await session.commit()
            print(
                f"Demo RBAC users present: {len(SEEDS)}; created this run: {created}; "
                f"memberships created: {membership_count}; office={OFFICE_SLUG}."
            )
            print("No passwords were generated or printed. Use Keycloak password reset for login.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
