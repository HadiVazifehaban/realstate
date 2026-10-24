"""``SyncOutbox`` -- transactional outbox for offline-first cloud sync.

Every MLS-share / collaboration / price-update event is written *inside* the
same DB transaction as the local mutation, guaranteeing zero data loss when the
internet is down.  A background worker later drains the queue to the cloud hub.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field, Column

from app.models.base import pg_enum, timestamp_column, utcnow, uuid_column
from app.models.enums import AggregateType, SyncStatus

_AggCol = Column(pg_enum(AggregateType, "aggregate_type"), nullable=False, index=True)
_StatusCol = Column(
    pg_enum(SyncStatus, "sync_status"),
    nullable=False,
    index=True,
    default=SyncStatus.PENDING,
)
# JSONB on PostgreSQL, plain JSON elsewhere (e.g. SQLite in unit tests).
_PayloadCol = Column(
    JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict
)


class SyncOutbox(SQLModel, table=True):
    """A single queued synchronisation event."""

    __tablename__ = "sync_outbox"

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    aggregate_type: AggregateType = Field(sa_column=_AggCol)
    aggregate_id: uuid.UUID | None = Field(default=None, index=True)

    # Sanitised, owner-free payload ready for MLS sharing.
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=_PayloadCol)

    status: SyncStatus = Field(default=SyncStatus.PENDING, sa_column=_StatusCol)
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=10)
    last_error: str | None = Field(default=None, max_length=1024)

    idempotency_key: str | None = Field(default=None, max_length=128, index=True)

    next_retry_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    processed_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=timestamp_column(index=True)
    )
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())

    @property
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries
