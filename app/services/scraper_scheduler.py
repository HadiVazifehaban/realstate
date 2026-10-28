"""Autonomous scrape scheduler (Phase 2b).

Fires a periodic sweep over ``SCRAPER_CITIES x SCRAPER_CATEGORIES`` so the CRM
keeps itself current without an operator clicking "trigger".

Operational rules, in order of importance:

1. **License gate** — a node without a usable license never schedules work,
   mirroring the ``verify_license_active`` guard on the HTTP endpoints.
2. **Single runner** — the app may run with ``--workers N``; a Postgres
   advisory lock ensures exactly one worker schedules a given tick.
3. **No overlap** — a city whose previous scheduled job is still PENDING or
   RUNNING is skipped, so a slow crawl cannot pile up.
4. **Never crash the loop** — any error is logged and the next tick proceeds.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
from datetime import date
from typing import Any, AsyncIterator

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.enums import ScrapeJobStatus, ScrapeJobTrigger
from app.models.scrape_job import ScrapeJob
from app.schemas.scraper import ScrapeJobCreate
from app.services import scraper_service

logger = get_logger("app.scraper.scheduler")

# Arbitrary but fixed key; shared by every worker of this application.
_SCHEDULER_LOCK_KEY = 918_273_645

_ACTIVE_STATUSES = (ScrapeJobStatus.PENDING, ScrapeJobStatus.RUNNING)


async def _has_active_job(
    session: AsyncSession, city: str, category: str, source: str | None = None
) -> bool:
    """True when a PENDING/RUNNING job already covers this city+category.

    Scoped by source when one is given. Without that scope a Delta job would mask
    the Divar job for the same city/category and the scheduler would run only
    whichever portal happened to be scheduled first.
    """
    conditions = [
        ScrapeJob.city == city,
        ScrapeJob.category == category,
        ScrapeJob.status.in_(_ACTIVE_STATUSES),
    ]
    if source:
        conditions.append(ScrapeJob.source == source)
    result = await session.execute(select(ScrapeJob.id).where(*conditions).limit(1))
    return result.scalar_one_or_none() is not None


async def _license_usable(session: AsyncSession, settings: Settings) -> bool:
    """Best-effort license check; never raises."""
    try:
        from app.services import license_service

        row = await license_service.sync_license_from_disk(session, settings)
        return bool(row.is_usable)
    except Exception as exc:  # noqa: BLE001 - never block the loop
        logger.warning("scheduler license check failed: %s", exc)
        return False


@contextlib.asynccontextmanager
async def _scheduler_lock(session: AsyncSession) -> AsyncIterator[bool]:
    """Hold a Postgres advisory lock so only one worker schedules a tick.

    On backends without ``pg_try_advisory_lock`` (e.g. the SQLite test suite)
    the lock is a no-op that reports ``True``.
    """
    try:
        acquired = await session.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": _SCHEDULER_LOCK_KEY}
        )
        yield bool(acquired.scalar())
    except Exception as exc:  # noqa: BLE001 - dialect without advisory locks
        logger.debug("advisory lock unavailable (%s); running unlocked", exc)
        yield True
    finally:
        with contextlib.suppress(Exception):
            await session.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": _SCHEDULER_LOCK_KEY}
            )


class ScrapeScheduler:
    """Periodic, license-gated scrape scheduler."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        rng: random.Random | None = None,
        session_factory: Any = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._tick_date = date.today().isoformat()
        self._rng = rng or random.Random()
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        # Injectable so tests (and future CLI sweeps) can run on another DB.
        self._session_factory = session_factory

    def _sessions(self) -> Any:
        """Return an async-session context manager bound to the target DB.

        ``session_factory`` may be an ``async_sessionmaker`` (call it) or an
        already-built async context manager (use it directly).
        """
        factory = self._session_factory
        if factory is None:
            from app.db.session import AsyncSessionLocal

            factory = AsyncSessionLocal
        if hasattr(factory, "__call__") and not hasattr(factory, "__aenter__"):
            return factory()
        return factory

    # ------------------------------------------------------------------ public
    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def interval_seconds(self) -> float:
        base = max(self.settings.scraper_schedule_interval_minutes, 1) * 60.0
        jitter = max(self.settings.scraper_schedule_jitter_seconds, 0)
        return base + (self._rng.uniform(0, jitter) if jitter else 0.0)

    async def tick(self) -> list[ScrapeJob]:
        """Run one scheduling pass; returns the jobs that were created."""
        s = self.settings
        if not s.scraper_enabled or not s.scraper_scheduler_enabled:
            logger.debug("scheduler disabled; tick skipped")
            return []

        created: list[ScrapeJob] = []
        batch_seen: set[tuple[str, str, str, str]] = set()
        async with self._sessions() as session:
            if not await _license_usable(session, s):
                logger.info("scheduler tick skipped: license not usable")
                return []

            async with _scheduler_lock(session) as acquired:
                if not acquired:
                    logger.debug("scheduler tick skipped: another worker holds the lock")
                    return []

                sources = s.source_list
                if not sources:
                    logger.warning(
                        "scheduler tick found no crawlable source; "
                        "check SCRAPER_SOURCES and the source registry"
                    )
                    return []
                logger.debug(
                    "scheduler tick covering sources=%s",
                    ",".join(sources),
                )

                for source in sources:
                    source_cities = list(s.city_list)
                    if source in {"delta", "sheypoor"}:
                        from app.services.scraper.demand_locations import demand_location, source_city_targets

                        source_cities = []
                        for configured_city in s.city_list:
                            location = demand_location(configured_city)
                            if location is None and configured_city.isascii():
                                from app.services.scraper.demand_locations import canonical_demand_city

                                location = canonical_demand_city(configured_city)
                            target = source_city_targets(location["id"]).get(source) if location else None
                            if target:
                                source_cities.append(target)
                    for city in source_cities:
                        for category in s.category_list:
                            try:
                                from app.services.scraper.category_mapping import resolve_categories

                                resolution = resolve_categories(source, category)
                                source_category = resolution.categories[0]
                            except ValueError:
                                # create_job performs the structured rejection;
                                # calculate the source category here only for
                                # intra-batch duplicate suppression.
                                source_category = category
                            target_key = (source, city, source_category, "SEARCH")
                            if target_key in batch_seen:
                                continue
                            batch_seen.add(target_key)
                            schedule_city, job_category = city, category
                            schedule_category = source_category
                            if s.scraper_schedule_skip_overlapping and await _has_active_job(
                                session, city, category, source
                            ):
                                logger.info("skipping %s/%s/%s: active job exists", source, city, category)
                                continue
                            if source in {"sheypoor", "delta"}:
                                schedule_category = source_category
                            job = await self._schedule_one(
                                session, schedule_city, job_category, source,
                                source_category=schedule_category if source in {"sheypoor", "delta"} else None,
                            )
                            if job is not None:
                                created.append(job)
        if created:
            logger.info(
                "scheduler tick created %d job(s)",
                len(created),
                extra={"jobs": len(created)},
            )
        return created

    async def _schedule_one(
        self, session: AsyncSession, city: str, category: str, source: str,
        source_category: str | None = None,
    ) -> ScrapeJob | None:
        s = self.settings
        try:
            if s.scraper_schedule_skip_overlapping and await _has_active_job(
                session, city, category, source
            ):
                logger.info(
                    "skipping %s/%s/%s: a job is still active", source, city, category
                )
                return None
            params = {"execution_scope": f"schedule:{self._tick_date}"}
            if source_category and source in {"sheypoor", "delta"}:
                params["source_category"] = source_category
            payload = ScrapeJobCreate(
                # Without this the job fell back to the node default and every
                # sweep crawled Divar only, no matter which portals were set up.
                source=source,
                city=city,
                category=category,
                params=params,
                max_pages=max(s.scraper_schedule_max_pages, 1),
                fetch_phones=False,
            )
            job = await scraper_service.trigger_with_trigger(
                session,
                payload,
                trigger=ScrapeJobTrigger.SCHEDULED,
                settings=s,
                wait=False,
            )
        except Exception as exc:  # noqa: BLE001 - one bad triple must not stop the rest
            logger.warning(
                "scheduler failed to queue %s/%s/%s: %s",
                source, city, category, exc,
            )
            return None

        scraper_service.launch_job_background(job.id, dict(job.params or {}))
        logger.info(
            "scheduled %s/%s/%s as job %s",
            source,
            city,
            category,
            job.id,
            extra={"event": "scrape_scheduled", "source": source},
        )
        return job

    async def run_forever(self) -> None:
        """Loop until :meth:`stop` is called, sleeping between ticks."""
        delay = max(self.settings.scraper_schedule_initial_delay_seconds, 0)
        logger.info(
            "scraper scheduler starting (first tick in %ss)",
            delay,
            extra={"delay": delay},
        )
        if delay:
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=delay)
        while not self._stopping.is_set():
            try:
                await self.tick()
            except Exception as exc:  # noqa: BLE001 - the loop must survive
                logger.error("scheduler tick failed: %s", exc)
            interval = self.interval_seconds()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=interval)

    def start(self) -> asyncio.Task | None:
        """Spawn the background loop (idempotent)."""
        if self.running:
            return self._task
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("no running loop; scheduler not started")
            return None
        self._stopping.clear()
        self._task = loop.create_task(self.run_forever(), name="scrape-scheduler")
        return self._task

    async def stop(self, timeout: float = 5.0) -> None:
        """Signal the loop to finish the current tick and await it."""
        self._stopping.set()
        if self._task is not None:
            with contextlib.suppress(asyncio.TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(self._task, timeout=timeout)
            self._task = None


def build_scheduler(settings: Settings | None = None, **kwargs: Any) -> ScrapeScheduler:
    """Factory used by the app lifespan (kept for testability)."""
    return ScrapeScheduler(settings, **kwargs)


__all__ = ["ScrapeScheduler", "build_scheduler"]