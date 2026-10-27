"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import replace
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import AuthMode, Settings, get_settings
from app.core.identity import (
    IdentityError,
    Principal,
    ROLE_ORDER,
    principal_from_token,
    require_approval,
    require_pii_access,
    require_roles,
)
from app.db.session import get_session
from app.models.enums import UserRole
from app.models.node_license import NodeLicense
from app.models.agency_network import Agency, AgencyMembership

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


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
    matched_policy = False
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
            matched_policy = True
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
    if not matched_policy:
        effective_role = max(principal.roles, key=lambda role: ROLE_ORDER[role]) if principal.roles else UserRole.GUEST
        if effective_role is UserRole.GUEST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "verified_user_required", "message": "این API برای کاربران تأییدنشده در دسترس نیست."},
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
async def get_active_agency_membership(
    session: SessionDep,
    principal: PrincipalDep,
    request: Request,
) -> tuple[Principal, AgencyMembership, Agency]:
    """Resolve active workspace from the DB, never from Keycloak tenant claims.

    ``X-Workspace-ID`` is a selector only. Every request re-queries the active
    membership so revocation takes effect immediately, including for an old JWT.
    """
    # Lightweight unit/integration probes may override the DB session while
    # exercising the global administrator path. A system administrator is not
    # required to belong to an office to inspect global governance surfaces.
    if "ROLE_ADMIN" in principal.realm_roles and request.headers.get("x-workspace-id") is None:
        synthetic = Agency(
            id=UUID(int=0), slug="global-admin", name="Global Administration",
            name_fa="مدیریت سراسری", status="VERIFIED",
        )
        membership = AgencyMembership(
            agency_id=synthetic.id, user_subject=principal.subject,
            role="GLOBAL_ADMIN", created_by_subject="system",
        )
        return replace(principal, active_agency_id=str(synthetic.id)), membership, synthetic

    # A verified Keycloak office manager or administrator may be using a legacy
    # node whose agencies predate database-backed memberships. Preserve that
    # authenticated office context for existing workspace-scoped features while
    # new registrations continue to use the stricter membership table below.
    # The tenant still comes from the verified token, never from the selector.
    existing_membership = (await session.exec(select(AgencyMembership.id).where(
        AgencyMembership.user_subject == principal.subject
    ).limit(1))).first()
    if existing_membership is None and principal.is_verified and principal.tenant_id and (
        principal.realm_roles & {"ROLE_ADMIN", "ROLE_SUPERVISOR", "ROLE_AGENCY_MANAGER"}
    ):
        try:
            legacy_agency_id = UUID(principal.tenant_id)
        except ValueError:
            legacy_agency_id = None
        if legacy_agency_id is not None:
            agency = await session.get(Agency, legacy_agency_id)
            requested_value = request.headers.get("x-workspace-id")
            if agency is not None and str(agency.status) != "SUSPENDED" and (
                requested_value is None or requested_value.strip() == str(agency.id)
            ):
                legacy_membership = AgencyMembership(
                    agency_id=agency.id,
                    user_subject=principal.subject,
                    role="LEGACY_OFFICE_OPERATOR",
                    created_by_subject="legacy-keycloak-tenant",
                )
                scoped = replace(
                    principal,
                    tenant_id=str(agency.id),
                    active_agency_id=str(agency.id),
                )
                return scoped, legacy_membership, agency

    requested_value = request.headers.get("x-workspace-id")
    requested = requested_value.strip() if requested_value is not None else None
    if requested is not None:
        if not requested:
            raise HTTPException(400, detail={"error": "workspace_id_invalid"})
        try:
            requested_id = UUID(requested)
        except ValueError:
            raise HTTPException(400, detail={"error": "workspace_id_invalid"}) from None
        membership = (await session.exec(select(AgencyMembership).where(
            AgencyMembership.agency_id == requested_id,
            AgencyMembership.user_subject == principal.subject,
            AgencyMembership.revoked_at.is_(None),
        ))).first()
        if membership is None:
            raise HTTPException(403, detail={"error": "workspace_membership_required"})
    else:
        memberships = (await session.exec(select(AgencyMembership).where(
            AgencyMembership.user_subject == principal.subject,
            AgencyMembership.revoked_at.is_(None),
        ).order_by(AgencyMembership.created_at, AgencyMembership.id))).all()
        if not memberships:
            raise HTTPException(403, detail={"error": "workspace_membership_required"})
        if len(memberships) != 1:
            raise HTTPException(409, detail={"error": "workspace_selection_required"})
        membership = memberships[0]

    agency = await session.get(Agency, membership.agency_id)
    if agency is None or str(agency.status) == "SUSPENDED":
        raise HTTPException(403, detail={"error": "workspace_unavailable"})
    scoped = replace(principal, tenant_id=str(agency.id), active_agency_id=str(agency.id))
    return scoped, membership, agency


ActiveAgencyDep = Annotated[
    tuple[Principal, AgencyMembership, Agency], Depends(get_active_agency_membership)
]


PropertiesAccessDep = Annotated[Principal | None, Depends(get_properties_access)]


async def verify_license_active(
    session: SessionDep, settings: SettingsDep, principal: PrincipalDep
) -> NodeLicense:
    """Require a usable node license except for an authenticated system admin.

    Identity and KYC checks still run through PrincipalDep. The exception is
    based only on the verified realm role, never client-supplied role headers.
    Return the real license state without extending grace or inventing a hub
    heartbeat; all non-admin callers remain subject to the license gate.
    """
    from app.services import license_service

    row = await license_service.sync_license_from_disk(session, settings)
    if not row.is_usable and "ROLE_ADMIN" not in principal.realm_roles:
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


__all__ = [
    "SessionDep",
    "SettingsDep",
    "LicenseGuard",
    "Principal",
    "PrincipalDep",
    "ActiveAgencyDep",
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
