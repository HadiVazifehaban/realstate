#!/usr/bin/env python3
"""Remove only the Phase 1.5 disposable fixture after an explicit confirmation."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401
from app.core.config import NodeMode, Settings
from app.models.agency_network import Agency, AgencyMembership
from app.models.agency_user import AgencyUser
from app.models.billing import AgencySubscription
from app.models.property import Property
from app.services import keycloak_admin


BATCH = "phase15-20261028"
PREFIX = f"{BATCH}-"
AGENCY_PREFIX = f"{BATCH}-office-"


def _settings() -> Settings:
    if os.getenv("PHASE15_TEST_CLEANUP_CONFIRM") != "YES":
        raise SystemExit("Set PHASE15_TEST_CLEANUP_CONFIRM=YES for the disposable fixture only.")
    database_url = os.getenv("PHASE15_TEST_DATABASE_URL", "")
    issuer = os.getenv("PHASE15_TEST_KEYCLOAK_ISSUER", "")
    if not database_url or "phase15" not in database_url or "phase15" not in issuer.lower():
        raise SystemExit("Refusing cleanup without explicit Phase 1.5 database and issuer URLs.")
    return Settings(
        node_mode=NodeMode.LOCAL,
        database_url=database_url,
        keycloak_issuer=issuer,
        keycloak_realm=os.getenv("PHASE15_TEST_KEYCLOAK_REALM", ""),
        keycloak_admin_client_id=os.getenv("PHASE15_TEST_KEYCLOAK_CLIENT_ID", ""),
        keycloak_admin_client_secret=os.getenv("PHASE15_TEST_KEYCLOAK_CLIENT_SECRET", ""),
    )


async def main() -> None:
    settings = _settings()
    dry_run = os.getenv("PHASE15_TEST_CLEANUP_DRY_RUN") == "YES"
    engine = create_async_engine(settings.database_url.replace("+psycopg", "+asyncpg"))
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    deleted_users = 0
    try:
        users = await keycloak_admin.list_directory_users(settings)
        for user in users:
            if user.email.casefold().startswith(PREFIX):
                if not dry_run:
                    await keycloak_admin.delete_user(settings, user.id)
                deleted_users += 1

        async with maker() as session:
            agencies = list((await session.exec(
                select(Agency).where(Agency.slug.like(f"{AGENCY_PREFIX}%"))
            )).all())
            agency_ids = [agency.id for agency in agencies]
            properties = list((await session.exec(
                select(Property).where(Property.source_ref.like(f"{BATCH}:%"))
            )).all())
            property_ids = [prop.id for prop in properties]
            # ListingShare intentionally has no FK to Property; delete rows by
            # batch property ids before deleting the properties themselves.
            if property_ids and not dry_run:
                from app.models.network_collab import ListingShare
                await session.exec(delete(ListingShare).where(ListingShare.property_id.in_(property_ids)))
                await session.exec(delete(Property).where(Property.id.in_(property_ids)))
            if agency_ids and not dry_run:
                await session.exec(delete(AgencyMembership).where(AgencyMembership.agency_id.in_(agency_ids)))
                await session.exec(delete(AgencySubscription).where(AgencySubscription.agency_id.in_([str(i) for i in agency_ids])))
                await session.exec(delete(Agency).where(Agency.id.in_(agency_ids)))
            if not dry_run:
                await session.exec(delete(AgencyUser).where(AgencyUser.username.like(f"{PREFIX}%")))
                await session.commit()
        action = "would remove" if dry_run else "removed"
        print(f"Phase 1.5 fixture {action}: users={deleted_users}, offices={len(agency_ids)}, properties={len(property_ids)}, batch={BATCH}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
