"""Allowlisted Keycloak Admin REST client using the caller's verified token.

This intentionally differs from the legacy service-account directory client:
the signed-in user's bearer token is forwarded unchanged so Keycloak enforces
that user's own realm-management permissions. No credential elevation occurs.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core.config import Settings

_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()


class KeycloakAdminApiError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


async def get_client() -> httpx.AsyncClient:
    """Return a process-shared bounded connection pool."""
    global _client
    async with _client_lock:
        if _client is None or _client.is_closed:
            _client = httpx.AsyncClient(
                timeout=httpx.Timeout(8.0, connect=3.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
                follow_redirects=False,
            )
        return _client


def _admin_root(settings: Settings, realm: str) -> str:
    """Derive a fixed upstream origin and permit only the configured realm."""
    if realm != settings.keycloak_realm:
        raise KeycloakAdminApiError(403, "realm_forbidden", "دسترسی به این Realm مجاز نیست.")
    issuer = settings.keycloak_issuer.strip().rstrip("/")
    parts = urlsplit(issuer)
    if parts.scheme != "https" or not parts.netloc or parts.username or parts.password:
        raise KeycloakAdminApiError(503, "keycloak_unavailable", "نشانی امن Keycloak پیکربندی نشده است.")
    if parts.path.rstrip("/") != f"/realms/{settings.keycloak_realm}" or parts.query or parts.fragment:
        raise KeycloakAdminApiError(503, "keycloak_unavailable", "Realm مدیریت با Realm احراز هویت یکسان نیست.")
    return f"{parts.scheme}://{parts.netloc}/admin/realms/{settings.keycloak_realm}"


def _safe_error(status_code: int) -> KeycloakAdminApiError:
    mappings = {
        401: ("session_expired", "نشست احراز هویت منقضی شده است."),
        403: ("keycloak_admin_permission_required", "مجوز مدیریتی لازم در Keycloak برای این عملیات وجود ندارد."),
        404: ("not_found", "منبع در Keycloak پیدا نشد."),
        409: ("conflict", "این تغییر با وضعیت فعلی Keycloak سازگار نیست."),
        400: ("keycloak_validation_failed", "اطلاعات ارسالی با قواعد Keycloak سازگار نیست."),
        422: ("keycloak_validation_failed", "اطلاعات ارسالی با قواعد Keycloak سازگار نیست."),
        429: ("keycloak_rate_limited", "تعداد درخواست‌ها بیش از حد مجاز است."),
    }
    code, message = mappings.get(status_code, ("keycloak_unavailable", "پاسخ معتبر از Keycloak دریافت نشد."))
    return KeycloakAdminApiError(status_code if status_code in mappings else 502, code, message)


def _operation_path(operation: str) -> str:
    """Closed GET-only operation map; arbitrary upstream paths are impossible."""
    fixed = {
        "GET:realm": "",
        "GET:users": "/users",
        "GET:groups": "/groups",
        "GET:roles": "/roles",
        "GET:clients": "/clients",
        "GET:client-scopes": "/client-scopes",
        "GET:authentication": "/authentication/flows",
        "GET:identity-providers": "/identity-provider/instances",
        "GET:user-federation": "/components",
        "GET:events": "/events",
        "GET:admin-events": "/admin-events",
        "GET:users/count": "/users/count",
        "GET:groups/count": "/groups/count",
        "GET:roles/count": "/roles/count",
        "GET:clients/count": "/clients/count",
        "GET:client-scope-count": "/client-scopes/count",
    }
    if operation in fixed:
        return fixed[operation]
    match = re.fullmatch(r"GET:(user|group|role|client|client-scope):([A-Za-z0-9._:-]{1,255})", operation)
    if match:
        kind, identity = match.groups()
        base = {"user": "users", "group": "groups", "role": "roles", "client": "clients", "client-scope": "client-scopes"}[kind]
        return f"/{base}/{identity}"
    raise KeycloakAdminApiError(400, "operation_not_allowed", "این عملیات در پنل مدیریتی مجاز نیست.")


async def admin_request(
    settings: Settings,
    access_token: str,
    realm: str,
    operation: str,
    *,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | list[Any] | None = None,
    client: httpx.AsyncClient | None = None,
) -> Any:
    """Send an allowlisted request with the user's already-verified bearer."""
    if not access_token or len(access_token) > 16_384:
        raise KeycloakAdminApiError(401, "authentication_required", "نشست احراز هویت معتبر نیست.")
    root = _admin_root(settings, realm)
    path = _operation_path(operation)
    http = client or await get_client()
    try:
        response = await http.request(
            "GET", f"{root}{path}", params=params, json=payload,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
    except httpx.TimeoutException as exc:
        raise KeycloakAdminApiError(504, "keycloak_timeout", "پاسخ Keycloak در مهلت مقرر دریافت نشد.") from exc
    except httpx.HTTPError as exc:
        raise KeycloakAdminApiError(502, "keycloak_unavailable", "ارتباط با Keycloak برقرار نشد.") from exc
    if response.status_code not in {200, 201, 202, 204}:
        raise _safe_error(response.status_code)
    if not response.content:
        return {"status": "ok"}
    try:
        return response.json()
    except ValueError:
        raise KeycloakAdminApiError(502, "invalid_keycloak_response", "پاسخ Keycloak معتبر نیست.") from None


__all__ = ["KeycloakAdminApiError", "admin_request"]