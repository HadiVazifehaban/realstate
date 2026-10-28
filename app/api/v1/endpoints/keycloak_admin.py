"""Session-token-only, system-admin Keycloak administration API."""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from app.api.deps import PrincipalDep, SettingsDep
from app.core.identity import Principal
from app.services.keycloak_admin_session import KeycloakAdminApiError, admin_request

router = APIRouter()
logger = logging.getLogger("app.api.keycloak_admin")
_WINDOW = 60
_LIMIT = 60
_request_windows: dict[str, tuple[int, int]] = {}
_RESOURCE_PERMISSIONS: dict[str, frozenset[str]] = {
    "GET:realm": frozenset({"view-realm", "manage-realm"}),
    "GET:users": frozenset({"view-users", "query-users", "manage-users"}),
    "GET:users/count": frozenset({"view-users", "query-users", "manage-users"}),
    "GET:groups": frozenset({"view-users", "query-groups", "manage-users"}),
    "GET:groups/count": frozenset({"view-users", "query-groups", "manage-users"}),
    "GET:roles": frozenset({"view-realm", "view-clients", "manage-realm", "manage-clients"}),
    "GET:roles/count": frozenset({"view-realm", "view-clients", "manage-realm", "manage-clients"}),
    "GET:clients": frozenset({"view-clients", "manage-clients"}),
    "GET:clients/count": frozenset({"view-clients", "manage-clients"}),
    "GET:client-scopes": frozenset({"view-clients", "manage-clients"}),
    "GET:client-scope-count": frozenset({"view-clients", "manage-clients"}),
    "GET:clients/count": frozenset({"view-clients", "manage-clients"}),
    "GET:users/count": frozenset({"view-users", "query-users", "manage-users"}),
    "GET:groups/count": frozenset({"view-users", "query-groups", "manage-users"}),
    "GET:roles/count": frozenset({"view-realm", "view-clients", "manage-realm", "manage-clients"}),
    "GET:authentication": frozenset({"view-realm", "manage-realm"}),
    "GET:admin-permissions": frozenset({"view-realm", "manage-realm"}),
    "GET:admin-permissions": frozenset({"view-realm", "manage-realm"}),
    "GET:identity-providers": frozenset({"view-identity-providers", "manage-identity-providers", "view-realm", "manage-realm"}),
    "GET:user-federation": frozenset({"view-realm", "manage-realm"}),
    "GET:events": frozenset({"view-events", "manage-events", "view-realm", "manage-realm"}),
    "GET:admin-events": frozenset({"view-events", "manage-events", "view-realm", "manage-realm"}),
}


def _guard(request: Request, principal: Principal, operation: str | None = None) -> str:
    # This is intentionally Realm Role only: client roles and similarly named
    # claims never satisfy the system administrator gate.
    if "ROLE_ADMIN" not in principal.realm_roles:
        raise HTTPException(403, detail={"error": "system_admin_required"})
    # A valid user access token must independently carry realm-management roles.
    # We never substitute the existing backend service-account credential.
    required = _RESOURCE_PERMISSIONS.get(operation or "GET:realm", frozenset())
    if not required or not principal.client_roles.get("realm-management", frozenset()).intersection(required):
        raise HTTPException(403, detail={"error": "keycloak_admin_permission_required"})

    now = int(time.time())
    key = principal.subject
    start, count = _request_windows.get(key, (now, 0))
    if now - start >= _WINDOW:
        start, count = now, 0
    if count >= _LIMIT:
        raise HTTPException(429, detail={"error": "admin_rate_limit"})
    _request_windows[key] = (start, count + 1)
    return key


def _audit(request: Request, actor: str, operation: str, outcome: str) -> None:
    # No request/response bodies, bearer tokens, credentials, or query values.
    logger.info("keycloak_admin_operation", extra={
        "event": "keycloak_admin_operation", "actor_subject": actor[:128],
        "operation": operation, "outcome": outcome,
        "client_ip": request.client.host if request.client else None,
    })


async def _call(request: Request, settings: SettingsDep, principal: PrincipalDep,
                token: str, operation: str, *, params: dict[str, Any] | None = None,
                payload: dict[str, Any] | list[Any] | None = None,
                realm: str | None = None) -> Any:
    actor = _guard(request, principal, operation)
    realm = realm or settings.keycloak_realm
    try:
        result = await admin_request(settings, token, realm, operation, params=params, payload=payload)
    except KeycloakAdminApiError as exc:
        _audit(request, actor, operation.split(":", 1)[0], "denied_or_failed")
        raise HTTPException(exc.status_code, detail={"error": exc.code, "message": exc.message}) from exc
    _audit(request, actor, operation.split(":", 1)[0], "success")
    return result


def _access_token(request: Request) -> str:
    # Principal dependency already cryptographically validated this bearer.
    # Requiring the original Authorization header here ensures no service token
    # or client-asserted credential is ever substituted.
    authorization = request.headers.get("authorization", "")
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        raise HTTPException(401, detail={"error": "authentication_required"})
    return value


class RealmOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    realm: str | None = None
    displayName: str | None = None
    enabled: bool | None = None
    registrationAllowed: bool | None = None
    resetPasswordAllowed: bool | None = None
    bruteForceProtected: bool | None = None


@router.get("/realms/{realm}")
async def realm_info(realm: str, request: Request, settings: SettingsDep, principal: PrincipalDep):
    if realm != settings.keycloak_realm:
        raise HTTPException(403, detail={"error": "realm_forbidden"})
    raw = await _call(request, settings, principal, _access_token(request), "GET:realm", realm=realm)
    return RealmOut.model_validate(raw)


def _safe_rows(value: Any, *, limit: int) -> dict[str, Any]:
    rows = value if isinstance(value, list) else []
    # Return only allowlisted, non-secret fields; never expose raw KC DTOs.
    fields = ("id", "username", "email", "firstName", "lastName", "enabled", "emailVerified", "createdTimestamp", "name", "path", "clientId", "protocol", "publicClient", "redirectUris", "webOrigins", "description", "composite", "containerId", "providerId", "alias", "providerType", "type", "operationType", "resourceType", "time", "userId", "userName", "ipAddress", "authenticator", "provider")
    clean = [{key: row[key] for key in fields if key in row} for row in rows[:limit] if isinstance(row, dict)]
    return {"items": clean, "count": len(clean), "limit": limit, "truncated": len(rows) > limit}


def _safe_tree(value: Any, *, depth: int = 0) -> dict[str, Any]:
    if not isinstance(value, dict) or depth > 12:
        return {}
    fields = ("id", "name", "path", "subGroupCount", "attributes")
    result = {key: value[key] for key in fields if key in value}
    children = value.get("subGroups")
    if isinstance(children, list):
        result["subGroups"] = [_safe_tree(child, depth=depth + 1) for child in children[:100]]
    return result


@router.get("/realms")
async def list_realms(request: Request, settings: SettingsDep, principal: PrincipalDep):
    _guard(request, principal)
    # Only the configured, authenticated realm is allowlisted.
    return await _call(request, settings, principal, _access_token(request), "GET:realm", realm=settings.keycloak_realm)


@router.get("/realms/{realm}/realm-settings")
async def realm_settings(realm: str, request: Request, settings: SettingsDep, principal: PrincipalDep):
    result = await _call(request, settings, principal, _access_token(request), "GET:realm", realm=realm)
    if not isinstance(result, dict):
        return {}
    fields = ("realm", "displayName", "enabled", "registrationAllowed", "resetPasswordAllowed", "rememberMe", "verifyEmail", "loginWithEmailAllowed", "duplicateEmailsAllowed", "editUsernameAllowed", "bruteForceProtected", "permanentLockout", "failureFactor", "waitIncrementSeconds", "maxFailureWaitSeconds", "minimumQuickLoginWaitSeconds", "quickLoginCheckMilliSeconds", "maxDeltaTimeSeconds", "attributes")
    return {key: result[key] for key in fields if key in result}


@router.get("/realms/{realm}/{resource}")
async def list_resource(
    realm: str, resource: str, request: Request, settings: SettingsDep,
    principal: PrincipalDep, first: int = Query(0, ge=0), max: int = Query(1, ge=1, le=100),
    search: str | None = Query(None, max_length=128), enabled: bool | None = None,
):
    operations = {
        "users": "GET:users", "groups": "GET:groups", "roles": "GET:roles",
        "clients": "GET:clients", "client-scopes": "GET:client-scopes",
        "authentication": "GET:authentication", "identity-providers": "GET:identity-providers",
        "user-federation": "GET:user-federation", "events": "GET:events",
        "admin-events": "GET:admin-events", "admin-permissions": "GET:realm",
    }
    operation = operations.get(resource)
    if not operation:
        raise HTTPException(404, detail={"error": "resource_not_found"})
    permission_operation = {
        "users": "GET:users", "groups": "GET:groups", "roles": "GET:roles",
        "clients": "GET:clients", "client-scopes": "GET:client-scopes",
        "authentication": "GET:authentication", "identity-providers": "GET:identity-providers",
        "user-federation": "GET:user-federation", "events": "GET:events",
        "admin-events": "GET:admin-events", "admin-permissions": "GET:admin-permissions",
    }[resource]
    _guard(request, principal, permission_operation)
    params: dict[str, Any] = {"first": first, "max": max}
    if search:
        params["search"] = search
    if enabled is not None and resource == "users":
        params["enabled"] = enabled
    result = await _call(request, settings, principal, _access_token(request), operation, params=params, realm=realm)
    if resource == "groups":
        rows = result if isinstance(result, list) else []
        return {"items": [_safe_tree(row) for row in rows[:max] if isinstance(row, dict)], "limit": max, "truncated": len(rows) > max}
    if resource == "authentication":
        rows = result if isinstance(result, list) else []
        return {"items": [{k: row[k] for k in ("id", "alias", "description", "providerId", "builtIn") if k in row} for row in rows[:max] if isinstance(row, dict)], "count": len(rows[:max]), "limit": max, "truncated": len(rows) > max}
    if resource == "admin-permissions":
        _guard(request, principal, "GET:admin-permissions")
        realm_settings = result if isinstance(result, dict) else {}
        return {"realm": settings.keycloak_realm, "keycloakVersion": realm_settings.get("attributes", {}).get("keycloakVersion"), "userRealmRoles": sorted(principal.realm_roles), "realmManagementClientRoles": sorted(principal.client_roles.get("realm-management", frozenset())), "fineGrainedAdminPermissions": realm_settings.get("adminPermissionsEnabled")}
    return _safe_rows(result, limit=max)


@router.get("/realms/{realm}/{resource}/{resource_id}")
async def get_resource(realm: str, resource: str, resource_id: str, request: Request,
                      settings: SettingsDep, principal: PrincipalDep):
    kind = {"users": "user", "groups": "group", "roles": "role", "clients": "client", "client-scopes": "client-scope"}.get(resource)
    if not kind:
        raise HTTPException(404, detail={"error": "resource_not_found"})
    if not resource_id or len(resource_id) > 255 or any(ord(c) < 32 for c in resource_id):
        raise HTTPException(422, detail={"error": "invalid_resource_id"})
    result = await _call(request, settings, principal, _access_token(request), f"GET:{kind}:{resource_id}", realm=realm)
    return _safe_rows([result], limit=1)["items"][0] if isinstance(result, dict) else {}


@router.get("/dashboard")
async def dashboard(request: Request, settings: SettingsDep, principal: PrincipalDep):
    actor = _guard(request, principal, "GET:realm")
    token = _access_token(request)
    results: dict[str, Any] = {}
    for name, operation in (("users", "GET:users/count"), ("groups", "GET:groups/count"), ("roles", "GET:roles/count"), ("clients", "GET:clients/count"), ("clientScopes", "GET:client-scope-count")):
        try:
            permission_operation = operation.replace("/count", "")
            _guard(request, principal, permission_operation)
            value = await admin_request(settings, token, settings.keycloak_realm, operation)
            results[name] = value.get("count") if isinstance(value, dict) else value[0].get("count") if isinstance(value, list) and value and isinstance(value[0], dict) else None
        except KeycloakAdminApiError as exc:
            results[name] = None
            if exc.status_code == 401:
                raise HTTPException(401, detail={"error": exc.code, "message": exc.message}) from exc
            logger.info("keycloak_admin_metric_unavailable", extra={"event": "keycloak_admin_metric_unavailable", "metric": name, "status": exc.status_code})
    _audit(request, actor, "dashboard_read", "success")
    return {"realm": settings.keycloak_realm, "metrics": results, "adminPermissions": {"systemRole": "ROLE_ADMIN", "realmManagementRoles": sorted(principal.client_roles.get("realm-management", frozenset()))}}


@router.get("/config")
async def panel_config(request: Request, settings: SettingsDep, principal: PrincipalDep):
    _guard(request, principal)
    return {"realm": settings.keycloak_realm}
