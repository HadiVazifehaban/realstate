"""Persistence + lifecycle for the node's commercial license.

Bridges the pure logic in :mod:`app.core.licensing` with the ``NodeLicense``
table so the whole system has a single source of truth for its lock state.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import Settings, get_settings
from app.core.licensing import (
    LicenseEvaluation,
    LicenseManager,
    LicenseStatus,
)
from app.models.node_license import NodeLicense


def _to_dt(ts: int | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def build_manager(settings: Settings | None = None) -> LicenseManager:
    """Create a :class:`LicenseManager` from application settings."""
    s = settings or get_settings()
    return LicenseManager(
        license_file=s.resolve_path(s.license_file),
        public_key_file=s.resolve_path(s.license_public_key_file),
        grace_days=s.offline_grace_days,
        fingerprint_override=s.machine_fingerprint_override or None,
    )


async def get_or_create_license_row(
    session: AsyncSession, settings: Settings | None = None
) -> NodeLicense:
    """Return the singleton ``NodeLicense`` row, creating it if necessary."""
    row = (await session.exec(select(NodeLicense).limit(1))).first()
    if row is not None:
        return row
    s = settings or get_settings()
    row = NodeLicense(grace_days=s.offline_grace_days)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def sync_license_from_disk(
    session: AsyncSession, settings: Settings | None = None
) -> NodeLicense:
    """Import the on-disk license token (if any) and refresh the DB row."""
    s = settings or get_settings()
    manager = build_manager(s)
    row = await get_or_create_license_row(session, s)

    token = manager.read_token()
    evaluation = manager.evaluate(
        last_heartbeat_at=int(row.last_heartbeat_at.timestamp()) if row.last_heartbeat_at else None,
    )
    _apply_evaluation(row, evaluation, token, s)
    await session.commit()
    await session.refresh(row)
    return row


async def evaluate_and_store(
    session: AsyncSession,
    *,
    last_heartbeat_at: int | None = None,
    settings: Settings | None = None,
) -> NodeLicense:
    """Evaluate the license now and persist the resulting status."""
    s = settings or get_settings()
    manager = build_manager(s)
    row = await get_or_create_license_row(session, s)

    if last_heartbeat_at is None and row.last_heartbeat_at is not None:
        last_heartbeat_at = int(row.last_heartbeat_at.timestamp())

    evaluation = manager.evaluate(last_heartbeat_at=last_heartbeat_at)
    _apply_evaluation(row, evaluation, manager.read_token(), s)
    await session.commit()
    await session.refresh(row)
    return row


async def record_heartbeat(
    session: AsyncSession, *, settings: Settings | None = None
) -> NodeLicense:
    """Mark a successful hub heartbeat and extend the offline grace window."""
    s = settings or get_settings()
    row = await get_or_create_license_row(session, s)
    now = datetime.now(timezone.utc)
    row.last_heartbeat_at = now
    row.offline_grace_deadline = now + timedelta(days=s.offline_grace_days)
    await session.commit()
    return await evaluate_and_store(
        session, last_heartbeat_at=int(now.timestamp()), settings=s
    )


def _apply_evaluation(
    row: NodeLicense,
    evaluation: LicenseEvaluation,
    token: str | None,
    settings: Settings,
) -> None:
    """Copy an evaluation onto the persisted row."""
    row.status = evaluation.status
    row.status_reason = evaluation.reason
    row.offline_grace_deadline = _to_dt(evaluation.offline_grace_deadline)
    row.grace_days = settings.offline_grace_days
    if token:
        row.license_key_signed = token
    payload = evaluation.payload
    if payload is not None:
        row.agency_name = payload.agency_name
        row.license_id = payload.license_id
        row.max_concurrent_users = payload.max_concurrent_users
        row.machine_fingerprint_hash = payload.machine_fingerprint_hash
        row.features = ",".join(payload.features)
        row.issued_at = _to_dt(payload.issued_at)
        row.expires_at = _to_dt(payload.expires_at)
    row.updated_at = datetime.now(timezone.utc)


def is_locked(status: LicenseStatus) -> bool:
    """Whether the given status should block normal operation."""
    return status in (
        LicenseStatus.EXPIRED,
        LicenseStatus.OFFLINE_GRACE_EXPIRED,
        LicenseStatus.LOCKED_HARDWARE_MISMATCH,
        LicenseStatus.NOT_INSTALLED,
        LicenseStatus.INVALID_SIGNATURE,
    )
