import httpx
import pytest

from app.api import deps
from app.core.config import AuthMode, Settings, get_settings


@pytest.mark.asyncio
async def test_property_reads_and_writes_always_require_identity(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    principal = object()
    resolver = AsyncMock(return_value=principal)
    monkeypatch.setattr(deps, "get_principal", resolver)
    settings = object()

    for method, path in [
        ("GET", "/api/v1/properties"),
        ("GET", "/api/v1/properties/cities"),
        ("GET", "/api/v1/properties/123"),
        ("POST", "/api/v1/properties"),
    ]:
        request = SimpleNamespace(method=method, url=SimpleNamespace(path=path))
        assert await deps.get_properties_access(request, settings) is principal
    assert resolver.await_count == 4


@pytest.mark.asyncio
async def test_legacy_license_mode_fails_closed_for_private_api():
    from starlette.requests import Request
    from fastapi import HTTPException

    request = Request({"type": "http", "method": "GET", "path": "/api/v1/users", "headers": []})
    with pytest.raises(HTTPException) as exc:
        await deps.get_principal(request, Settings(auth_mode=AuthMode.LICENSE))
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_health_is_public_while_data_apis_require_a_keycloak_bearer(monkeypatch):
    from fastapi import FastAPI
    from app.api.v1.router import api_router

    probe_app = FastAPI()
    probe_app.include_router(api_router, prefix="/api/v1")
    monkeypatch.setitem(
        probe_app.dependency_overrides,
        get_settings,
        lambda: Settings(
            auth_mode=AuthMode.KEYCLOAK,
            keycloak_issuer="https://id.example/realms/maskanchi",
        ),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=probe_app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        assert (await client.get("/api/v1/health")).status_code == 200
        for path in (
            "/api/v1/health/detailed",
            "/api/v1/properties",
            "/api/v1/gis/cities",
            "/api/v1/license/status",
            "/api/v1/users",
            "/api/v1/otp/audit/09120000000",
            "/api/v1/auth/applications",
        ):
            response = await client.get(path)
            assert response.status_code == 401, (path, response.status_code)


def test_sensitive_api_families_enforce_existing_realm_roles():
    from types import SimpleNamespace

    from app.api.deps import require_api_permissions
    from app.core.identity import Principal
    from app.models.enums import SaasTier, UserRole
    from fastapi import HTTPException

    manager = Principal(
        subject="manager",
        realm_roles=frozenset({"ROLE_AGENCY_MANAGER"}),
        roles=frozenset({UserRole.OFFICE_MANAGER}),
        kyc_status="VERIFIED",
        saas_tier=SaasTier.PRO,
    )
    require_api_permissions(
        manager,
        SimpleNamespace(url=SimpleNamespace(path="/api/v1/network/agencies")),
    )
    with pytest.raises(HTTPException) as exc:
        require_api_permissions(
            manager,
            SimpleNamespace(url=SimpleNamespace(path="/api/v1/license/status")),
        )
    assert exc.value.status_code == 403
