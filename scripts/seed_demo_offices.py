#!/usr/bin/env python3
"""Seed five clearly labeled pending demo offices for local UI testing.

This intentionally creates office directory rows only. It does not invent
Keycloak users or memberships, so the offices are not login/chat workspaces.

Run from the backend container: python scripts/seed_demo_offices.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401
from app.core.config import get_settings
from app.models.agency_network import Agency
from app.models.enums import AgencyStatus
from app.services.agency_referrals import ensure_agency_referral_code


def _async_url(value: str) -> str:
    return value.replace("+psycopg", "+asyncpg") if "+psycopg" in value else value


async def main() -> None:
    settings = get_settings()
    if settings.node_mode.value != "LOCAL":
        raise SystemExit("Refusing to seed demo offices outside NODE_MODE=LOCAL.")

    engine = create_async_engine(_async_url(settings.database_url))
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    created = 0
    try:
        async with maker() as session:
            for index in range(1, 6):
                slug = f"demo100-office-{index:02d}"
                row = (await session.exec(select(Agency).where(Agency.slug == slug))).first()
                if row is not None:
                    continue
                row = Agency(
                    slug=slug,
                    name=f"Demo Chat Office {index:02d}",
                    name_fa=f"دفتر آزمایشی گفتگو {index:02d}",
                    city="تهران",
                    district="آزمایشی",
                    description="دفتر آزمایشی؛ فاقد عضویت و دسترسی چت.",
                    status=AgencyStatus.PENDING,
                )
                session.add(row)
                await session.flush()
                await ensure_agency_referral_code(session, row)
                created += 1
            await session.commit()

        count = len((await session.exec(select(Agency).where(
            Agency.slug.like("demo100-office-%")
        ))).all())
        print(f"Demo offices present: {count}; created this run: {created}.")
        print("All are PENDING directory entries; no accounts, memberships, or chat access were created.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())