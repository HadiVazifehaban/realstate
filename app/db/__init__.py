"""Database package: engine, sessions and optional bootstrap helpers."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal, engine, get_session, metadata
from app.models import *  # noqa: F401,F403  (re-export for convenience)

__all__ = ["AsyncSessionLocal", "engine", "get_session", "metadata", "create_all", "enable_postgis"]


async def enable_postgis(session: AsyncSession) -> None:
    """Ensure the PostGIS extension is available (no-op if already installed)."""
    await session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    await session.commit()


async def create_all() -> None:
    """Create all tables directly from metadata (dev / tests only).

    Production deployments use Alembic migrations instead.
    """
    async with engine.begin() as conn:
        await conn.run_sync(metadata().create_all)
