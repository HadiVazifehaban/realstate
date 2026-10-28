"""Security boundaries for the user-session Keycloak Admin REST client."""

from __future__ import annotations

import pytest
import httpx
from fastapi import HTTPException
from starlette.requests import Request

from app.core.config import Settings
from app.services.keycloak_admin_session import KeycloakAdminApiError, _admin_root, _operation_path, admin_request
from app.api.v1.endpoints.keycloak_admin import _guard
from app.core.identity import Principal


def _settings(**changes) -> Settings:
    values = {"keycloak_issuer": "https://id.example.test/realms/tenant-a", "keycloak_realm": "tenant-a"}
    values.update(changes)
    return Settings(**values)


def test_admin_root_is_fixed_to_configured_realm() -> None:
    assert _admin_root(_settings(), "tenant-a") == "https://id.example.test/admin/realms/tenant-a"
    with pytest.raises(KeycloakAdminApiError) as error:
        _admin_root(_settings(), "tenant-b")
    assert error.value.status_code == 403


@pytest.mark.parametrize("issuer", [
    "https://id.example.test/realms/other",
    "https://user:pass@id.example.test/realms/tenant-a",
    "http://id.example.test/realms/tenant-a",
    "https://id.example.test/realms/tenant-a?redirect=bad",
])
def test_admin_root_rejects_insecure_or_injected_issuer(issuer: str) -> None:
    settings = _settings(keycloak_issuer=issuer)
    with pytest.raises(KeycloakAdminApiError):
        _admin_root(settings, "tenant-a")


def test_admin_root_rejects_http_even_when_general_debug_is_enabled() -> None:
    with pytest.raises(KeycloakAdminApiError):
        _admin_root(_settings(keycloak_issuer="http://id.example.test/realms/tenant-a", debug=True), "tenant-a")


def test_operation_routes_are_allowlisted_and_identifiers_validated() -> None:
    assert _operation_path("GET:users") == "/users"
    assert _operation_path("GET:user:abc-123") == "/users/abc-123"
    with pytest.raises(KeycloakAdminApiError):
        _operation_path("GET:https://attacker.test")
    with pytest.raises(KeycloakAdminApiError):
        _operation_path("GET:user:../../other-realm")


@pytest.mark.asyncio
async def test_admin_request_forwards_user_token_without_logging_or_leaking_response() -> None:
    seen: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers["authorization"]
        return httpx.Response(200, json=[{"id": "u1"}])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await admin_request(_settings(), "user-access-token", "tenant-a", "GET:users", params={"first": 0, "max": 10}, client=client)
    assert seen["url"].startswith("https://id.example.test/admin/realms/tenant-a/users?")
    assert seen["authorization"] == "Bearer user-access-token"
    assert result == [{"id": "u1"}]


@pytest.mark.asyncio
async def test_keycloak_forbidden_is_mapped_without_upstream_body() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="sensitive upstream diagnostic")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(KeycloakAdminApiError) as error:
            await admin_request(_settings(), "token", "tenant-a", "GET:users", client=client)
    assert error.value.status_code == 403
    assert "sensitive" not in error.value.message


def test_system_admin_role_must_be_a_realm_role_not_a_client_role() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/api/v1/admin/keycloak"})
    with pytest.raises(HTTPException) as denied:
        _guard(request, Principal(subject="x", realm_roles=frozenset(), client_roles={"some-client": frozenset({"ROLE_ADMIN"})}))
    assert denied.value.status_code == 403


def test_realm_admin_without_keycloak_admin_permission_is_denied() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/api/v1/admin/keycloak"})
    with pytest.raises(HTTPException) as denied:
        _guard(request, Principal(subject="x", realm_roles=frozenset({"ROLE_ADMIN"})))
    assert denied.value.status_code == 403


def test_each_operation_requires_a_specific_keycloak_permission() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/api/v1/admin/keycloak"})
    principal = Principal(subject="x", realm_roles=frozenset({"ROLE_ADMIN"}), client_roles={"realm-management": frozenset({"view-users"})})
    assert _guard(request, principal, "GET:users") == "x"
    with pytest.raises(HTTPException) as denied:
        _guard(request, Principal(subject="y", realm_roles=frozenset({"ROLE_ADMIN"}), client_roles={"realm-management": frozenset({"view-users"})}), "GET:clients")
    assert denied.value.status_code == 403


def test_admin_rate_limit_is_applied_after_permission_checks() -> None:
    from app.api.v1.endpoints import keycloak_admin

    request = Request({"type": "http", "method": "GET", "path": "/api/v1/admin/keycloak"})
    principal = Principal(subject="rate-test", realm_roles=frozenset({"ROLE_ADMIN"}), client_roles={"realm-management": frozenset({"view-users"})})
    original = keycloak_admin._request_windows.copy()
    try:
        keycloak_admin._request_windows["rate-test"] = (int(__import__("time").time()), keycloak_admin._LIMIT)
        with pytest.raises(HTTPException) as denied:
            _guard(request, principal, "GET:users")
        assert denied.value.status_code == 429
    finally:
        keycloak_admin._request_windows.clear()
        keycloak_admin._request_windows.update(original)