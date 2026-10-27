from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import Depends, FastAPI

from app.api import deps
from app.core.config import AuthMode, Settings, get_settings
from app.core.identity import Principal
from app.core.licensing import LicenseStatus
from app.models.enums import UserRole
from app.models.node_license import NodeLicense
from app.services import license_service


@pytest.fixture
def probe(monkeypatch):
    app = FastAPI()
    settings = Settings(auth_mode=AuthMode.KEYCLOAK)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[deps.get_session] = lambda: None
    row = NodeLicense(status=LicenseStatus.OFFLINE_GRACE_EXPIRED)
    sync = AsyncMock(return_value=row)
    monkeypatch.setattr(license_service, "sync_license_from_disk", sync)

    @app.get("/protected", dependencies=[Depends(deps.verify_license_active)])
    async def protected():
        return {"ok": True}

    return app, row, sync


@pytest.mark.parametrize("status", list(LicenseStatus))
async def test_verified_admin_can_access_without_changing_license(probe, status):
    app, row, sync = probe
    row.status = status
    app.dependency_overrides[deps.get_principal] = lambda: Principal(
        subject="admin", realm_roles=frozenset({"ROLE_ADMIN"}),
        roles=frozenset({UserRole.ADMIN}), kyc_status="VERIFIED",
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected")
    assert response.status_code == 200
    assert row.status == status
    assert row.last_heartbeat_at is None
    sync.assert_awaited_once()


@pytest.mark.parametrize("role", ["ROLE_SUPERVISOR", "ROLE_AGENCY_MANAGER", "ROLE_SENIOR_BROKER", "financial_admin"])
async def test_non_admin_cannot_bypass_license_with_role_headers(probe, role):
    app, _, _ = probe
    app.dependency_overrides[deps.get_principal] = lambda: Principal(
        subject="other", realm_roles=frozenset({role}), kyc_status="VERIFIED",
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"X-User-Role": "ADMIN"})
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "license_not_active"


async def test_no_token_cannot_claim_admin(probe):
    app, _, sync = probe
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"X-User-Role": "ADMIN"})
    assert response.status_code == 401
    sync.assert_not_awaited()


async def test_pending_admin_still_requires_approval(probe, monkeypatch):
    app, _, sync = probe
    monkeypatch.setattr(deps, "principal_from_token", AsyncMock(return_value=Principal(
        subject="pending", realm_roles=frozenset({"ROLE_ADMIN"}),
        roles=frozenset({UserRole.ADMIN}), kyc_status="PENDING",
    )))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": "Bearer test"})
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "kyc_pending"
    sync.assert_not_awaited()


async def test_admin_lead_feed_works_with_expired_offline_grace(probe, monkeypatch):
    from app.api.v1.router import api_router
    from app.services import crm as crm_service

    app, row, _ = probe
    app.include_router(api_router, prefix="/api/v1")
    app.dependency_overrides[deps.get_principal] = lambda: Principal(
        subject="admin", realm_roles=frozenset({"ROLE_ADMIN"}),
        roles=frozenset({UserRole.ADMIN}), kyc_status="VERIFIED",
    )
    listing = AsyncMock(return_value=[])
    monkeypatch.setattr(crm_service, "list_leads", listing)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/crm/leads")
    assert response.status_code == 200, response.text
    assert response.json() == {"count": 0, "items": []}
    assert row.status == LicenseStatus.OFFLINE_GRACE_EXPIRED
    listing.assert_awaited_once()