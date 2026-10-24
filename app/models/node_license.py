"""``NodeLicense`` -- commercial license state persisted on the office node."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import SQLModel, Field, Column

from app.core.licensing import LicenseStatus
from app.models.base import pg_enum, timestamp_column, utcnow, uuid_column

# SQLModel column definitions -------------------------------------------------
_StatusCol = Column(pg_enum(LicenseStatus, "license_status"), nullable=False, index=True)


class NodeLicense(SQLModel, table=True):
    """The single commercial license row bound to this physical machine."""

    __tablename__ = "node_license"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    machine_fingerprint_hash: str = Field(default="", index=True, max_length=128)
    license_key_signed: str = Field(default="", description="Signed AVG1 token")
    agency_name: str = Field(default="", max_length=255)
    max_concurrent_users: int = Field(default=1)
    license_id: str = Field(default="", max_length=128)
    features: str = Field(default="", description="Comma separated feature flags")

    issued_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    expires_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    last_heartbeat_at: datetime | None = Field(
        default=None, sa_column=timestamp_column(nullable=True)
    )
    offline_grace_deadline: datetime | None = Field(
        default=None, sa_column=timestamp_column(nullable=True)
    )
    grace_days: int = Field(default=14)

    status: LicenseStatus = Field(default=LicenseStatus.NOT_INSTALLED, sa_column=_StatusCol)
    status_reason: str = Field(default="", max_length=512)

    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())

    # ------------------------------------------------------------------ helpers
    @property
    def is_usable(self) -> bool:
        return self.status in (LicenseStatus.ACTIVE, LicenseStatus.GRACE_PERIOD)

    def feature_list(self) -> list[str]:
        return [f.strip() for f in self.features.split(",") if f.strip()]
