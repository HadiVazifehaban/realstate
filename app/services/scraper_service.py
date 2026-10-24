"""Scraper service facade: job lifecycle + execution wiring (Phase 2).

The API layer stays thin; this module owns session handling, cipher setup,
job persistence and the async fan-out into :func:`run_search_job`.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.crypto import PiiCipher
from app.core.logging import get_logger
from app.models import ScrapeJob
from app.models.base import utcnow
from app.models.enums import (
    ScrapeJobKind,
    ScrapeJobStatus,
    ScrapeJobTrigger,
)
from app.schemas.scraper import ScrapeJobCreate
from app.services.ingestion.pipeline import run_search_job
from app.services.scraper.phone_extractor import PhoneExtractor
from app.services.scraper.registry import DEFAULT_SOURCE_KEY, get_source

logger = get_logger("app.services.scraper_service")

# One shared background task set so fire-and-forget jobs are not GC'd.
_background_tasks: set[asyncio.Task] = set()


def get_pii_cipher(settings: Settings | None = None) -> PiiCipher:
    """Load (or create) the per-agency Fernet key from the configured key file."""
    s = settings or get_settings()
    key_file = s.resolve_path(s.pii_key_file)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    return PiiCipher.from_key_file(key_file)


def build_cipher_for_tests() -> PiiCipher:
    """Ephemeral cipher for unit tests (never touches disk)."""
    return PiiCipher(PiiCipher.generate_key())


async def create_job(
    session: AsyncSession,
    payload: ScrapeJobCreate,
    *,
    trigger: ScrapeJobTrigger = ScrapeJobTrigger.API,
    triggered_by_id: UUID | None = None,
    settings: Settings | None = None,
) -> ScrapeJob:
    """Persist a PENDING scrape job row."""
    s = settings or get_settings()
    city = payload.city or (s.city_list[0] if s.city_list else "")
    category = payload.category or (s.category_list[0] if s.category_list else "")
    # Resolved (not merely stored) so an unknown portal fails here, at trigger
    # time, with a readable message instead of failing later inside the job.
    source = get_source(payload.source or None)
    job = ScrapeJob(
        kind=payload.kind,
        status=ScrapeJobStatus.PENDING,
        trigger=trigger,
        city=city,
        category=category,
        source=source.key,
        params={
            "max_pages": payload.max_pages,
            "fetch_phones": payload.fetch_phones,
            "requested_city": payload.city,
            "requested_category": payload.category,
            "districts": list(payload.districts),
        },
        triggered_by_id=triggered_by_id,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def get_job(session: AsyncSession, job_id: UUID) -> ScrapeJob | None:
    return await session.get(ScrapeJob, job_id)


async def list_jobs(
    session: AsyncSession, *, limit: int = 50, offset: int = 0
) -> tuple[list[ScrapeJob], int]:
    count_result = await session.execute(select(func.count()).select_from(ScrapeJob))
    total_value = int(count_result.scalar() or 0)
    result = await session.execute(
        select(ScrapeJob)
        .order_by(ScrapeJob.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    # ``scalars()`` unwraps single-entity rows into model instances regardless
    # of driver (psycopg Rows vs SQLModel's direct entities).
    entities: list[ScrapeJob] = list(result.scalars().all())
    return entities, total_value


async def _run_job_with_session(
    session: AsyncSession,
    job: ScrapeJob,
    payload_params: dict[str, Any],
    settings: Settings,
) -> None:
    """Drive one PENDING job to completion on an already-open session."""
    s = settings
    max_pages = int(payload_params.get("max_pages", 1) or 1)
    fetch_phones = bool(payload_params.get("fetch_phones", False))
    source = get_source(job.source or payload_params.get("source") or DEFAULT_SOURCE_KEY)
    cipher = get_pii_cipher(s)
    # Only Divar has the session-gated extractor; asking for phones elsewhere is
    # a no-op rather than a job that reports zero phones collected.
    phone_extractor = (
        PhoneExtractor(settings=s) if fetch_phones and source.supports_phone_extraction else None
    )
    if fetch_phones and not source.supports_phone_extraction:
        logger.warning(
            "job %s asked for phones but source %r has no extractor; skipping",
            job.id,
            source.key,
        )
    async with source.client_factory(settings=s) as client:
        await run_search_job(
            session,
            job,
            client=client,
            cipher=cipher,
            source=source,
            settings=s,
            phone_extractor=phone_extractor,
            max_pages=max_pages,
        )


async def execute_job(
    job_id: UUID,
    payload_params: dict[str, Any] | None = None,
    *,
    settings: Settings | None = None,
) -> None:
    """Run a persisted job to completion (used by the background task)."""
    from app.db.session import AsyncSessionLocal

    s = settings or get_settings()
    params = payload_params or {}

    async with AsyncSessionLocal() as session:
        job = await session.get(ScrapeJob, job_id)
        if job is None:
            logger.warning("scrape job %s vanished before execution", job_id)
            return
        if job.status != ScrapeJobStatus.PENDING:
            logger.info("scrape job %s already %s; skipping", job_id, job.status)
            return
        await _run_job_with_session(session, job, params, s)


async def recover_orphaned_jobs(session: AsyncSession) -> int:
    """Fail jobs left PENDING/RUNNING by a previous process.

    Jobs execute as in-process asyncio tasks, so any unclean shutdown (a
    restart, a crash, a redeploy) orphans whatever was in flight.  Without this
    sweep the scheduler's overlap guard would see those zombies as "active"
    forever and never queue another sweep -- the exact failure that leaves the
    radar empty after the first crawl.

    Safe to call on every boot: with nothing to recover it is a no-op.
    """
    rows = list(
        (
            await session.execute(
                select(ScrapeJob).where(
                    ScrapeJob.status.in_(
                        (ScrapeJobStatus.PENDING, ScrapeJobStatus.RUNNING)
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return 0
    now = utcnow()
    for job in rows:
        job.status = ScrapeJobStatus.FAILED
        job.error = "interrupted by node restart"
        job.finished_at = now
        job.updated_at = now
        session.add(job)
    await session.commit()
    logger.warning("recovered %d orphaned scrape job(s)", len(rows))
    return len(rows)


def launch_job_background(job_id: UUID, params: dict[str, Any]) -> None:
    """Schedule :func:`execute_job` without blocking the HTTP response."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop (tests / CLI): run synchronously is the caller's job.
        return
    task = loop.create_task(execute_job(job_id, params))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def trigger_and_maybe_run(
    session: AsyncSession,
    payload: ScrapeJobCreate,
    *,
    settings: Settings | None = None,
    wait: bool = False,
) -> ScrapeJob:
    """Create a job and either run it inline (tests) or in the background (API)."""
    s = settings or get_settings()
    job = await create_job(session, payload, trigger=ScrapeJobTrigger.API, settings=s)
    params = dict(job.params or {})
    if wait:
        # Inline execution (tests / CLI): reuse the caller's session so the
        # freshly-created job row is visible without a second DB connection.
        await _run_job_with_session(session, job, params, s)
        await session.refresh(job)
    else:
        launch_job_background(job.id, params)
    job.updated_at = utcnow()
    return job


__all__ = [
    "get_pii_cipher",
    "build_cipher_for_tests",
    "create_job",
    "get_job",
    "list_jobs",
    "execute_job",
    "recover_orphaned_jobs",
    "launch_job_background",
    "trigger_and_maybe_run",
]
