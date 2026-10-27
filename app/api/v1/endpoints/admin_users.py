"""System-admin-only Keycloak role and independent KYC administration."""

from fastapi import APIRouter, Body, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.deps import PrincipalDep, SessionDep, SettingsDep
from app.core.identity import KEYCLOAK_ROLE_MAP
from app.models.registration import AuthAuditLog
from app.services import keycloak_admin
from app.services.keycloak_admin import KeycloakDirectoryError

router = APIRouter()


class ApproveUserRequest(BaseModel):
    userId: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=8, max_length=500)


class SetUserRoleRequest(BaseModel):
    userId: str = Field(min_length=1, max_length=255)
    roleName: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=8, max_length=500)


@router.get("/users")
async def list_users(settings: SettingsDep):
    """List all users from Keycloak."""
    users = await keycloak_admin.list_directory_users(settings)
    
    # Convert to simple dict format
    user_list = []
    for user in users:
        user_list.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "enabled": user.enabled,
            "attributes": {
                "kyc_status": [user.kyc_status],
                "mobile_verified": ["true" if user.mobile_verified else "false"],
            },
            "realmRoles": list(user.realm_roles),
        })
    
    return {"users": user_list}


@router.post("/users/approve")
async def approve_user(
    settings: SettingsDep,
    session: SessionDep,
    principal: PrincipalDep,
    http_request: Request,
    request: ApproveUserRequest = Body(...),
):
    """Record KYC approval without changing the user's business/Realm role."""
    try:
        user = await keycloak_admin.set_kyc_status(settings, request.userId, "VERIFIED")
    except KeycloakDirectoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"error": exc.code, "message": exc.message}) from exc
    session.add(AuthAuditLog(
        event="admin.kyc.verified",
        keycloak_user_id=request.userId[:64],
        outcome="verified",
        detail=f"actor={principal.subject}; reason={request.reason.strip()}"[:1000],
        client_ip=http_request.client.host if http_request.client else "",
    ))
    await session.commit()
    return {
        "user_id": user.id,
        "kyc_status": user.kyc_status,
        "mobile_verified": user.mobile_verified,
        "realm_roles": sorted(user.realm_roles),
    }


@router.post("/users/role")
async def set_user_role(
    settings: SettingsDep,
    session: SessionDep,
    principal: PrincipalDep,
    http_request: Request,
    request: SetUserRoleRequest = Body(...),
):
    """Grant one allowlisted system Realm role with an audit record."""
    role = request.roleName.strip()
    if role not in KEYCLOAK_ROLE_MAP:
        raise HTTPException(status_code=422, detail={"error": "unknown_realm_role"})
    try:
        directory = await keycloak_admin.list_directory_users(settings)
        target = next((item for item in directory if item.id == request.userId), None)
        if target is None:
            raise HTTPException(status_code=404, detail="کاربر در Realm پیدا نشد.")
        if target.role.value == "ADMIN" and role != "ROLE_ADMIN":
            remaining = [item for item in directory if item.id != request.userId and item.enabled and item.role.value == "ADMIN"]
            if not remaining:
                raise HTTPException(status_code=409, detail={"error": "last_admin", "message": "نمی‌توان آخرین مدیر سامانه را تنزل داد."})
        await keycloak_admin._set_realm_roles(settings, request.userId, [role])
        await keycloak_admin.invalidate_user_sessions(settings, request.userId)
    except KeycloakDirectoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"error": exc.code, "message": exc.message}) from exc
    session.add(AuthAuditLog(
        event="admin.realm_role.changed",
        keycloak_user_id=request.userId[:64],
        outcome="changed",
        detail=f"actor={principal.subject}; role={role}; reason={request.reason.strip()}"[:1000],
        client_ip=http_request.client.host if http_request.client else "",
    ))
    await session.commit()
    return {"user_id": request.userId, "realm_roles": [role]}
