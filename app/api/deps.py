"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AuthMode, Settings, get_settings
from app.core.identity import (
    IdentityError,
    Principal,
    principal_from_token,
    require_approval,
    require_pii_access,
    require_roles,
)
from app.db.session import get_session
from app.models.enums import UserRole
from app.models.node_license import NodeLicense

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def verify_license_active(session: SessionDep, settings: SettingsDep) -> NodeLicense:
    """Gate a route behind a usable commercial license (Phase 1 contract).

    Raises ``403`` when the node is locked (expired, offline-grace-exceeded,
    hardware mismatch, missing or invalid license) so Phase 2+ features cannot
    be operated without a valid AVG license.
    """
    from app.services import license_service

    row = await license_service.sync_license_from_disk(session, settings)
    if not row.is_usable:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "license_not_active",
                "status": str(row.status),
                "reason": row.status_reason,
                "message": "A valid AVG license is required for this operation.",
            },
        )
    return row


LicenseGuard = Annotated[NodeLicense, Depends(verify_license_active)]

# Route-level role floors for especially sensitive areas. The endpoints keep
# their finer ownership/business checks; this table prevents authenticated but
# low-privilege users from entering administrative/operator surfaces at all.
ROUTE_ROLE_POLICIES: tuple[tuple[str, frozenset[str]], ...] = (
    ("/api/v1/admin", frozenset({"ROLE_ADMIN"})),
    ("/api/v1/license", frozenset({"ROLE_ADMIN"})),
    ("/api/v1/scraper", frozenset({"ROLE_ADMIN", "ROLE_SUPERVISOR"})),
    ("/api/v1/auth/applications", frozenset({"ROLE_ADMIN", "ROLE_SUPERVISOR"})),
    ("/api/v1/otp/audit", frozenset({"ROLE_ADMIN", "ROLE_SUPERVISOR"})),
    ("/api/v1/otp/status", frozenset({"ROLE_ADMIN", "ROLE_SUPERVISOR"})),
    (
        "/api/v1/properties",
        frozenset({"ROLE_ADMIN", "ROLE_SUPERVISOR", "ROLE_AGENCY_MANAGER", "ROLE_SENIOR_BROKER", "ROLE_JUNIOR_BROKER"}),
    ),
    (
        "/api/v1/matching",
        frozenset({"ROLE_ADMIN", "ROLE_SUPERVISOR", "ROLE_AGENCY_MANAGER", "ROLE_SENIOR_BROKER", "ROLE_JUNIOR_BROKER"}),
    ),
    (
        "/api/v1/crm",
        frozenset({"ROLE_ADMIN", "ROLE_SUPERVISOR", "ROLE_AGENCY_MANAGER", "ROLE_SENIOR_BROKER", "ROLE_JUNIOR_BROKER"}),
    ),
    (
        "/api/v1/network",
        frozenset({"ROLE_ADMIN", "ROLE_SUPERVISOR", "ROLE_AGENCY_MANAGER", "ROLE_SENIOR_BROKER"}),
    ),
    (
        "/api/v1/statistics",
        frozenset({"ROLE_ADMIN", "ROLE_SUPERVISOR", "ROLE_AGENCY_MANAGER", "ROLE_SENIOR_BROKER", "ROLE_DATA_ANALYST"}),
    ),
)


def require_api_permissions(principal: PrincipalDep, request: Request) -> Principal:
    """Enforce minimum Keycloak roles for administrative API families."""
    path = request.url.path.rstrip("/") or "/"
    is_financial_path = path == "/api/v1/admin/financial" or path.startswith(
        "/api/v1/admin/financial/"
    )
    # The general admin policy must not subsume the finance-only permission.
    policies = (
        tuple(item for item in ROUTE_ROLE_POLICIES if item[0] != "/api/v1/admin")
        if is_financial_path
        else ROUTE_ROLE_POLICIES
    )
    for prefix, allowed_roles in policies:
        if path == prefix or path.startswith(f"{prefix}/"):
            if (
                prefix == "/api/v1/properties"
                and request.method == "POST"
                and path == "/api/v1/properties"
                and "ROLE_OWNER" in principal.realm_roles
            ):
                return principal
            if not principal.realm_roles.intersection(allowed_roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "forbidden_role",
                        "message": "نقش شما اجازهٔ استفاده از این بخش را ندارد.",
                    },
                )
            break
    # This specific surface is finance-role-only and must be checked after the
    # broad admin prefix: a financial admin is intentionally not a ROLE_ADMIN.
    if is_financial_path:
        if not principal.realm_roles.intersection({"ROLE_ADMIN", "financial_admin"}):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "financial_admin_required",
                    "message": "دسترسی مدیر مالی لازم است.",
                },
            )
    return principal


# --------------------------------------------------------------------------- #
# Identity (Keycloak / OIDC)
# --------------------------------------------------------------------------- #
async def get_principal(
    request: Request,
    settings: SettingsDep,
) -> Principal:
    """Resolve the caller for a request.

    In ``KEYCLOAK`` mode the bearer token is the only accepted identity: it is
    verified against the realm, and the approval gate is applied here so no
    route can forget it.

    A licensed offline identity mode exists for legacy LAN deployments, but it
    cannot satisfy this API's Keycloak-only authorization contract. If it is
    selected here, fail closed rather than turning the bootstrap identity into
    an implicit API credential.
    """
    if settings.auth_mode is AuthMode.KEYCLOAK:
        token = _bearer_token(request)
        try:
            principal = await principal_from_token(token, settings)
            # The KYC gate lives here so no route can forget it. It raises
            # IdentityError too, so it shares the translation below -- without
            # this the approval refusal escapes as a 500 instead of a 403.
            require_approval(principal, settings)
            if not principal.roles:
                raise IdentityError(
                    403,
                    "role_required",
                    "برای دسترسی به این سرویس، نقش کاربری فعال لازم است.",
                )
        except IdentityError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"error": exc.code, "message": exc.message},
            ) from exc
        return principal

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": "keycloak_authentication_required",
            "message": "احراز هویت Keycloak برای این سرویس پیکربندی نشده است.",
        },
    )


async def get_properties_access(
    request: Request,
    settings: SettingsDep,
) -> Principal | None:
    """Resolve identity for every property operation, including feed reads."""
    return await get_principal(request, settings)


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "missing_token",
                "message": "توکن دسترسی ارائه نشده است.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token.strip()


def require_principal_roles(*roles: UserRole) -> Any:
    """Dependency factory: require one of ``roles`` from the caller."""
    allowed = frozenset(roles)

    async def _dependency(principal: PrincipalDep) -> Principal:
        try:
            require_roles(principal, allowed)
        except IdentityError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"error": exc.code, "message": exc.message},
            ) from exc
        return principal

    return _dependency


def require_pii_reader(principal: PrincipalDep) -> Principal:
    """Dependency: the caller may decrypt owner contacts."""
    try:
        require_pii_access(principal)
    except IdentityError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.code, "message": exc.message},
        ) from exc
    return principal


def require_governor(principal: PrincipalDep) -> Principal:
    """Dependency: the caller may override valuation or merge duplicates."""
    try:
        require_roles(
            principal,
            {UserRole.SUPERVISOR, UserRole.ADMIN},
            message="این عملیات تنها برای ناظر یا مدیر ارشد مجاز است.",
        )
    except IdentityError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.code, "message": exc.message},
        ) from exc
    return principal


def require_financial_admin(principal: PrincipalDep) -> Principal:
    """Require the dedicated finance realm role (or system administrator)."""
    from app.core.identity import FINANCIAL_ADMIN_ROLE

    if FINANCIAL_ADMIN_ROLE not in principal.realm_roles and "ROLE_ADMIN" not in principal.realm_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "financial_admin_required", "message": "دسترسی مدیر مالی لازم است."},
        )
    return principal


PrincipalDep = Annotated[Principal, Depends(get_principal)]
PropertiesAccessDep = Annotated[Principal | None, Depends(get_properties_access)]


__all__ = [
    "SessionDep",
    "SettingsDep",
    "LicenseGuard",
    "Principal",
    "PrincipalDep",
    "get_session",
    "verify_license_active",
    "get_principal",
    "require_api_permissions",
    "get_properties_access",
    "PropertiesAccessDep",
    "require_principal_roles",
    "require_pii_reader",
    "require_governor",
    "require_financial_admin",
]

