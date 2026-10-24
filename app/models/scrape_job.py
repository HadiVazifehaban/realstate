"""``ScrapeJob`` -- lifecycle record for a Divar autonomous ingestion run.

Each job tracks one SEARCH / DETAIL / PHONE scrape so the Phase 4 dashboard can
monitor progress, deduplication ratios and failures in real time.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field, Column

from app.models.base import pg_enum, timestamp_column, utcnow, uuid_column
from app.models.enums import ScrapeJobKind, ScrapeJobStatus, ScrapeJobTrigger

_KindCol = Column(pg_enum(ScrapeJobKind, "scrape_job_kind"), nullable=False)
_StatusCol = Column(
    pg_enum(ScrapeJobStatus, "scrape_job_status"), nullable=False, index=True
)
_TriggerCol = Column(pg_enum(ScrapeJobTrigger, "scrape_job_trigger"), nullable=False)
_ParamsCol = Column(
    JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict
)


class ScrapeJob(SQLModel, table=True):
    """One unit of scraper work (search sweep, detail fetch or phone extract)."""

    __tablename__ = "scrape_job"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    kind: ScrapeJobKind = Field(default=ScrapeJobKind.SEARCH, sa_column=_KindCol)
    status: ScrapeJobStatus = Field(default=ScrapeJobStatus.PENDING, sa_column=_StatusCol)
    trigger: ScrapeJobTrigger = Field(
        default=ScrapeJobTrigger.MANUAL, sa_column=_TriggerCol
    )

    city: str = Field(default="", max_length=64, index=True)
    category: str = Field(default="", max_length=128)
    #: Registry key of the portal this job crawls (``divar``, ``sheypoor``, ...).
    #: A plain string rather than a PG enum so registering a new source does not
    #: need a migration; ``app.services.scraper.registry`` owns the valid set.
    #: The literal is repeated from ``DEFAULT_SOURCE_KEY`` on purpose -- models
    #: must not import from ``services``.
    source: str = Field(default="divar", max_length=32, index=True)
    params: dict[str, Any] = Field(default_factory=dict, sa_column=_ParamsCol)

    # Progress counters (surfaced on the Phase 4 dashboard).
    pages_scraped: int = Field(default=0)
    items_found: int = Field(default=0)
    items_new: int = Field(default=0)
    items_duplicate: int = Field(default=0)
    items_failed: int = Field(default=0)

    error: str | None = Field(default=None, max_length=1024)
    triggered_by_id: uuid.UUID | None = Field(default=None, foreign_key="agency_user.id")

    started_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    finished_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=timestamp_column(index=True)
    )
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            ScrapeJobStatus.COMPLETED,
            ScrapeJobStatus.FAILED,
            ScrapeJobStatus.CANCELLED,
        )
