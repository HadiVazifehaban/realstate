"""Scraper service facade: job lifecycle + execution wiring (Phase 2).

The API layer stays thin; this module owns session handling, cipher setup,
job persistence and the async fan-out into :func:`run_search_job`.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
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
from app.services.scraper.category_mapping import (
    JobValidationError,
    resolve_categories,
    validate_job_target,
)

logger = get_logger("app.services.scraper_service")

# One shared background task set so fire-and-forget jobs are not GC'd.
_background_tasks: set[asyncio.Task] = set()
_execution_slots = asyncio.Semaphore(2)


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
    # Resolve and validate the effective target before touching persistence.
    # Generic categories are converted to the verified source-owned slug here,
    # so every caller (API, scheduler and demand collection) gets the same gate.
    requested_source = payload.source or DEFAULT_SOURCE_KEY
    try:
        mapping = validate_job_target(requested_source, city, category, s)
    except JobValidationError:
        # Legacy category compatibility must never bypass source/city checks.
        raise
    source = get_source(requested_source)
    if requested_source.strip().lower() == "delta":
        from app.services.scraper.delta_taxonomy import normalise_city

        try:
            city = normalise_city(city)
        except ValueError:
            # Existing callers may persist an unsupported placeholder; runtime
            # dispatch remains fail-closed in the client before network I/O.
            pass
    elif requested_source.strip().lower() == "divar":
        from app.services.scraper.cities import normalize_city_slug

        city = normalize_city_slug(city)
    source_category = mapping.categories[0]
    resolved_source_category = source_category

    # Demand collection already owns an explicit source crosswalk and passes a
    # source-specific slug. Keep canonical UI categories for all other jobs;
    # the worker resolves them to `source_category` at execution time.
    internal_demand = (
        payload.params.get("execution_scope", "").startswith("demand:")
        and payload.params.get("source_category") in mapping.categories
    )
    internal_schedule = (
        trigger == ScrapeJobTrigger.SCHEDULED
        and payload.params.get("execution_scope", "").startswith("schedule:")
        and payload.params.get("source_category") in mapping.categories
        and source.key == "sheypoor"
    )
    if payload.params.get("source_category") and not (internal_demand or internal_schedule):
        raise JobValidationError("UNSUPPORTED_CATEGORY", "source category override is reserved for internal mapped jobs")
    if payload.params.get("property_type_hint") is not None:
        raise JobValidationError("UNSUPPORTED_CATEGORY", "property type hints are not trusted for listing classification")
    if source.key == "divar" and category not in {
        "apartment-sell", "apartment-rent", "house-villa-sell", "house-villa-rent"
    }:
        from app.services.scraper.parser import map_category

        if map_category(category) is None:
            raise JobValidationError("UNSUPPORTED_CATEGORY", "Divar category is not recognized")
        source_category = category
    if internal_demand or internal_schedule:
        source_category = str(payload.params["source_category"]).strip().lower()
        try:
            mapping = resolve_categories(source.key, category)
            if source_category not in mapping.categories:
                raise JobValidationError("UNSUPPORTED_CATEGORY", "source category does not match verified mapping")
        except JobValidationError:
            from app.services.scraper.sheypoor_taxonomy import resolve_slug

            if source.key != "sheypoor" or resolve_slug(source_category) is None:
                raise
    if internal_demand:
        from app.services.scraper.demand_locations import source_city_targets

        location_id = payload.params["execution_scope"].split(":", 1)[1]
        expected = source_city_targets(location_id).get(source.key)
        if expected != city:
            raise JobValidationError("UNMAPPED_CITY", "demand execution city does not match curated source crosswalk")
    elif internal_schedule and source.key == "sheypoor":
        from app.services.scraper.demand_locations import demand_location

        city_row = demand_location(city)
        if city_row is None or city_row.get("slug") != city:
            raise JobValidationError("UNMAPPED_CITY", "scheduled Sheypoor city does not match curated source crosswalk")
    elif trigger == ScrapeJobTrigger.SCHEDULED and source.key == "sheypoor":
        source_category = resolved_source_category
    elif source.key == "sheypoor":
        from app.services.scraper.sheypoor_taxonomy import resolve_slug

        if resolve_slug(source_category) is None:
            raise JobValidationError("UNSUPPORTED_CATEGORY", "category has no verified Sheypoor taxonomy entry")
    effective_category = category
    effective_scope = str(payload.params.get("execution_scope") or "")

    # Serialize check/create for a target, then suppress only active duplicate
    # work. Completed work can be explicitly run again on a later trigger.
    bind = getattr(session, "bind", None)
    if bind is None:
        try:
            bind = session.get_bind()
        except Exception:
            bind = None
    if bind is not None and bind.dialect.name == "postgresql":
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"scrape-target:{source.key}:{city}:{effective_category}:{payload.kind.value}:{effective_scope}"},
        )
    duplicate = await session.execute(
        select(ScrapeJob).where(
            ScrapeJob.source == source.key,
            ScrapeJob.city == city,
            ScrapeJob.category == effective_category,
            ScrapeJob.kind == payload.kind,
            ScrapeJob.params["execution_scope"].as_string() == effective_scope,
            ScrapeJob.status.in_((ScrapeJobStatus.PENDING, ScrapeJobStatus.RUNNING)),
        ).limit(1)
    )
    existing = duplicate.scalar_one_or_none()
    if existing is not None:
        return existing

    job_params = {
        "max_pages": payload.max_pages,
        "fetch_phones": payload.fetch_phones,
        "requested_city": payload.city,
        "source_category": source_category,
        "execution_scope": effective_scope,
        "districts": list(payload.districts),
    }
    if payload.params.get("dry_run") is True:
        raise JobValidationError("DRY_RUN", "dry-run requests cannot persist or launch jobs")

    job = ScrapeJob(
        kind=payload.kind,
        status=ScrapeJobStatus.PENDING,
        trigger=trigger,
        city=city,
        category=effective_category,
        params=job_params,
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
    async def bounded_execute():
        # Persist PENDING first, then wait without holding a DB connection.
        # This cap is per worker process (not a distributed queue).
        async with _execution_slots:
            await execute_job(job_id, params)

    task = loop.create_task(bounded_execute())
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
