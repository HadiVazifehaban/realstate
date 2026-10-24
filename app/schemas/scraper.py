"""Scraper trigger / job schemas (Phase 2, Pydantic V2).

The Phase 4 dashboard drives these endpoints; validation is strict so a bad
neighbourhood sweep can never create an unbounded scrape job.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ScrapeJobKind, ScrapeJobStatus, ScrapeJobTrigger


class ScrapeJobCreate(BaseModel):
    """Request body for ``POST /api/v1/scraper/trigger``."""

    source: str = Field(
        default="",
        max_length=32,
        description=(
            "Registry key of the portal to crawl, e.g. 'divar' or 'sheypoor'. "
            "Empty means the node default."
        ),
    )
    city: str = Field(default="", max_length=64, description="City slug, e.g. tehran")
    """
    Several cities in one call, e.g. ``["tehran", "karaj"]``.

    The advisor's market is whatever they filtered the feed to, and a market is
    rarely one city: a Tehran desk works the capital and its satellites. Taking
    a list here means one click on «جست‌وجو با این فیلتر» queues a sweep per
    city, instead of the UI firing one request per city and racing them.
    """
    cities: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Several city slugs to sweep in one call; queued one job each.",
    )
    category: str = Field(
        default="",
        max_length=128,
        description="Category slug, e.g. apartment-sell",
    )
    districts: list[str] = Field(
        default_factory=list,
        max_length=25,
        description=(
            "Optional neighbourhood slugs to narrow the sweep, e.g. "
            "['tehran-saat-abad']. Empty means the whole city."
        ),
    )
    kind: ScrapeJobKind = ScrapeJobKind.SEARCH
    max_pages: int = Field(default=1, ge=1, le=50)
    fetch_phones: bool = Field(
        default=False,
        description=(
            "Also run the OTP-gated phone extractor. Only Divar has one; other "
            "sources skip this and log it."
        ),
    )

    @field_validator("source", "city", "category", "districts")
    @classmethod
    def _strip(cls, value):
        """Trim whitespace so ' tehran ' never reaches the registry."""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return value


class ScrapeJobResponse(BaseModel):
    """One scrape job with Phase 4 monitoring counters."""

    id: uuid.UUID
    kind: str
    status: str
    trigger: str
    source: str = "divar"
    city: str
    category: str
    params: dict = Field(default_factory=dict)
    pages_scraped: int = 0
    items_found: int = 0
    items_new: int = 0
    items_duplicate: int = 0
    items_failed: int = 0
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_job(cls, job) -> "ScrapeJobResponse":
        return cls(
            id=job.id,
            kind=job.kind.value if hasattr(job.kind, "value") else str(job.kind),
            status=job.status.value if hasattr(job.status, "value") else str(job.status),
            trigger=job.trigger.value if hasattr(job.trigger, "value") else str(job.trigger),
            source=getattr(job, "source", "") or "divar",
            city=job.city,
            category=job.category,
            params=dict(job.params or {}),
            pages_scraped=job.pages_scraped,
            items_found=job.items_found,
            items_new=job.items_new,
            items_duplicate=job.items_duplicate,
            items_failed=job.items_failed,
            error=job.error,
            started_at=job.started_at,
            finished_at=job.finished_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


class ScrapeJobListResponse(BaseModel):
    """Paginated wrapper for ``GET /api/v1/scraper/jobs``."""

    items: list[ScrapeJobResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


class ScrapeStatsResponse(BaseModel):
    """Aggregated scraper metrics for the operations dashboard (Phase 4)."""

    window_hours: int
    jobs: dict[str, int]
    items: dict[str, int]
    rates: dict[str, float]
    health: list[dict] = Field(default_factory=list)
    stuck: list[dict] = Field(default_factory=list)
    recent_errors: list[dict] = Field(default_factory=list)


__all__ = [
    "ScrapeJobCreate",
    "ScrapeJobResponse",
    "ScrapeJobListResponse",
    "ScrapeStatsResponse",
]
