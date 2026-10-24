"""License-related API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FingerprintResponse(BaseModel):
    """Machine identity disclosed to the license server during activation."""

    fingerprint_hash: str
    component_count: int
    platform: str


class LicenseStatusResponse(BaseModel):
    status: str
    is_usable: bool
    reason: str = ""
    node_mode: str
    agency_name: str | None = None
    license_id: str | None = None
    max_concurrent_users: int | None = None
    machine_fingerprint_hash: str | None = None
    features: list[str] = []
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    offline_grace_deadline: datetime | None = None
    grace_days: int = 14


class HeartbeatResponse(BaseModel):
    received: bool
    status: str
    last_heartbeat_at: datetime | None = None
    offline_grace_deadline: datetime | None = None
