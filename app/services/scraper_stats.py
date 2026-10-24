"""Aggregate scraper statistics for the Phase 4 monitoring dashboard.

Everything is computed in SQL (``GROUP BY`` / aggregate functions) so the cost
stays flat as the ``scrape_job`` table grows, instead of loading every job row
into Python.

Metrics exposed:

* **Totals** — jobs and items found/new/duplicate/failed within a time window.
* **Rates**  — duplicate and failure rates (what operations actually cares
  about: how much of the crawl is wasted).
* **Health** — per city+category counters, last run, and stuck detection.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ScrapeJobStatus
from app.models.scrape_job import ScrapeJob

# Statuses that mean "this pair is actively working".
_BUSY_STATUSES = (ScrapeJobStatus.PENDING, ScrapeJobStatus.RUNNING)


def _now() -> datetime:
    return datetime.now(tz=None).astimezone()


def _minutes_since(moment: datetime | None) -> int:
    """Whole minutes elapsed since ``moment``; 0 when unknown.

    Timestamps read back from some drivers (notably SQLite) are naive while
    ``_now()`` is tz-aware, so normalise before subtracting.
    """
    if moment is None:
        return 0
    reference = _now()
    if moment.tzinfo is None:
        moment = moment.astimezone()
    return max(int((reference - moment).total_seconds() // 60), 0)


def _window_start(hours: int) -> datetime:
    return _now() - timedelta(hours=max(hours, 1))


def _safe_rate(numerator: int | float, denominator: int | float) -> float:
    """Ratio clamped to [0, 1]; 0.0 when the denominator is zero."""
    if not denominator:
        return 0.0
    return round(min(max(numerator / denominator, 0.0), 1.0), 4)


async def collect_stats(session: AsyncSession, *, hours: int = 24) -> dict[str, Any]:
    """Aggregate counters for the last ``hours``."""
    since = _window_start(hours)

    totals = await session.execute(
        select(
            func.count(ScrapeJob.id),
            func.coalesce(func.sum(ScrapeJob.items_found), 0),
            func.coalesce(func.sum(ScrapeJob.items_new), 0),
            func.coalesce(func.sum(ScrapeJob.items_duplicate), 0),
            func.coalesce(func.sum(ScrapeJob.items_failed), 0),
        ).where(ScrapeJob.created_at >= since)
    )
    job_count, found, new, duplicate, failed = (int(v or 0) for v in totals.one())

    status_rows = await session.execute(
        select(ScrapeJob.status, func.count(ScrapeJob.id))
        .where(ScrapeJob.created_at >= since)
        .group_by(ScrapeJob.status)
    )
    by_status = {str(getattr(s, "value", s)): int(n) for s, n in status_rows.all()}

    return {
        "window_hours": max(hours, 1),
        "jobs": {
            "total": job_count,
            "completed": by_status.get("COMPLETED", 0),
            "failed": by_status.get("FAILED", 0),
            "running": by_status.get("RUNNING", 0),
            "pending": by_status.get("PENDING", 0),
            "cancelled": by_status.get("CANCELLED", 0),
        },
        "items": {
            "found": found,
            "new": new,
            "duplicate": duplicate,
            "failed": failed,
        },
        "rates": {
            "new": _safe_rate(new, found),
            "duplicate": _safe_rate(duplicate, found),
            "failure": _safe_rate(failed, found),
        },
    }


async def collect_city_health(
    session: AsyncSession, *, hours: int = 24, limit: int = 50
) -> list[dict[str, Any]]:
    """Per city+category health over the same window as :func:`collect_stats`.

    ``last_finished_at`` is reported in absolute time so an operator can still
    spot a stale feed even when its runs fall outside the window.
    """
    since = _window_start(hours)
    rows = await session.execute(
        select(
            ScrapeJob.city,
            ScrapeJob.category,
            func.count(ScrapeJob.id),
            func.coalesce(func.sum(ScrapeJob.items_found), 0),
            func.coalesce(func.sum(ScrapeJob.items_new), 0),
            func.coalesce(func.sum(ScrapeJob.items_duplicate), 0),
            func.coalesce(func.sum(ScrapeJob.items_failed), 0),
            func.max(ScrapeJob.started_at),
            func.max(ScrapeJob.finished_at),
            func.count(ScrapeJob.id).filter(
                ScrapeJob.status == ScrapeJobStatus.COMPLETED
            ),
            func.count(ScrapeJob.id).filter(
                ScrapeJob.status == ScrapeJobStatus.FAILED
            ),
        )
        .where(ScrapeJob.created_at >= since)
        .group_by(ScrapeJob.city, ScrapeJob.category)
        .order_by(func.max(ScrapeJob.created_at).desc())
        .limit(limit)
    )

    health: list[dict[str, Any]] = []
    for (
        city,
        category,
        total,
        found,
        new,
        duplicate,
        failed,
        last_started,
        last_finished,
        completed_runs,
        failed_runs,
    ) in rows.all():
        # "Healthy" means at least one run succeeded and none failed. A job that
        # finished *because it failed* must not read as healthy.
        health.append(
            {
                "city": city,
                "category": category,
                "jobs": int(total or 0),
                "runs_completed": int(completed_runs or 0),
                "runs_failed": int(failed_runs or 0),
                "items_found": int(found or 0),
                "items_new": int(new or 0),
                "duplicate_rate": _safe_rate(duplicate, found),
                "failure_rate": _safe_rate(failed, found),
                "last_started_at": last_started,
                "last_finished_at": last_finished,
                "healthy": bool(completed_runs) and not failed_runs,
            }
        )
    return health


async def find_stuck_pairs(
    session: AsyncSession, *, limit: int = 20
) -> list[dict[str, Any]]:
    """Pairs still PENDING/RUNNING, with how long they have been running.

    The overlap guard prevents piling up, so a long-running job is the visible
    symptom of a stuck scrape.
    """
    rows = await session.execute(
        select(
            ScrapeJob.city,
            ScrapeJob.category,
            ScrapeJob.status,
            ScrapeJob.started_at,
        )
        .where(ScrapeJob.status.in_(_BUSY_STATUSES))
        .order_by(ScrapeJob.created_at.asc())
        .limit(limit)
    )
    return [
        {
            "city": city,
            "category": category,
            "status": str(getattr(job_status, "value", job_status)),
            "started_at": started_at,
            "running_over_minutes": _minutes_since(started_at),
        }
        for city, category, job_status, started_at in rows.all()
    ]


async def collect_recent_errors(
    session: AsyncSession, *, limit: int = 10
) -> list[dict[str, Any]]:
    """The most recent FAILED jobs with their error text (truncated)."""
    rows = await session.execute(
        select(
            ScrapeJob.city,
            ScrapeJob.category,
            ScrapeJob.error,
            ScrapeJob.finished_at,
        )
        .where(ScrapeJob.status == ScrapeJobStatus.FAILED)
        .order_by(ScrapeJob.finished_at.desc().nullslast())
        .limit(limit)
    )
    return [
        {
            "city": city,
            "category": category,
            "error": (error or "")[:200] or None,
            "finished_at": finished_at,
        }
        for city, category, error, finished_at in rows.all()
    ]


__all__ = [
    "collect_stats",
    "collect_city_health",
    "find_stuck_pairs",
    "collect_recent_errors",
]