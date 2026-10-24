"""Commercial license endpoints (status, activation fingerprint, heartbeat)."""

from __future__ import annotations

import platform

from fastapi import APIRouter, HTTPException, status as http_status

from app.api.deps import SessionDep, SettingsDep
from app.schemas.license import (
    FingerprintResponse,
    HeartbeatResponse,
    LicenseStatusResponse,
)
from app.services import license_service

router = APIRouter()


def _to_response(row) -> LicenseStatusResponse:
    return LicenseStatusResponse(
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
        is_usable=row.is_usable,
        reason=row.status_reason,
        node_mode="",
        agency_name=row.agency_name or None,
        license_id=row.license_id or None,
        max_concurrent_users=row.max_concurrent_users,
        machine_fingerprint_hash=row.machine_fingerprint_hash or None,
        features=row.feature_list(),
        issued_at=row.issued_at,
        expires_at=row.expires_at,
        last_heartbeat_at=row.last_heartbeat_at,
        offline_grace_deadline=row.offline_grace_deadline,
        grace_days=row.grace_days,
    )


@router.get("/status", response_model=LicenseStatusResponse, summary="Current license (مجوز) status")
async def license_status(session: SessionDep, settings: SettingsDep) -> LicenseStatusResponse:
    row = await license_service.sync_license_from_disk(session, settings)
    response = _to_response(row)
    response.node_mode = settings.node_mode.value
    response.grace_days = settings.offline_grace_days
    return response


@router.get(
    "/machine-fingerprint",
    response_model=FingerprintResponse,
    summary="Hardware fingerprint for license (مجوز) issuing",
)
async def machine_fingerprint(settings: SettingsDep) -> FingerprintResponse:
    manager = license_service.build_manager(settings)
    fp = manager.machine_fingerprint()
    try:
        digest = fp.hash()
    except Exception as exc:  # noqa: BLE001 - surfaced as 409
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"Unable to derive hardware fingerprint: {exc}",
        ) from exc
    return FingerprintResponse(
        fingerprint_hash=digest,
        component_count=fp.component_count,
        platform=platform.platform(),
    )


@router.post("/heartbeat", response_model=HeartbeatResponse, summary="Record hub heartbeat - فارسی")
async def heartbeat(session: SessionDep, settings: SettingsDep) -> HeartbeatResponse:
    row = await license_service.record_heartbeat(session, settings=settings)
    return HeartbeatResponse(
        received=True,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
        last_heartbeat_at=row.last_heartbeat_at,
        offline_grace_deadline=row.offline_grace_deadline,
    )
