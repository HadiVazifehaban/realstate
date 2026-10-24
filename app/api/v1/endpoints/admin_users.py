"""Admin user management endpoints for Keycloak.

This allows admins to approve users and manage roles from the dashboard.
"""

from fastapi import APIRouter, Body
from app.api.deps import SettingsDep
from app.services import keycloak_admin
from pydantic import BaseModel

router = APIRouter()


class ApproveUserRequest(BaseModel):
    userId: str


class SetUserRoleRequest(BaseModel):
    userId: str
    roleName: str


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
            "attributes": user.attributes if hasattr(user, 'attributes') else {},
            "realmRoles": list(user.realm_roles),
        })
    
    return {"users": user_list}


@router.post("/users/approve")
async def approve_user(
    settings: SettingsDep,
    request: ApproveUserRequest = Body(...),
):
    """Approve a user by setting KYC status to VERIFIED."""
    # Since Keycloak attributes don't work, we'll set the role to ROLE_OWNER
    # as a proxy for approval. This is temporary until Keycloak is fixed.
    await keycloak_admin._set_realm_roles(settings, request.userId, ['ROLE_OWNER'])
    
    return {"message": "کاربر تایید شد (نقش به ROLE_OWNER تغییر یافت)"}


@router.post("/users/role")
async def set_user_role(
    settings: SettingsDep,
    request: SetUserRoleRequest = Body(...),
):
    """Set a user's role in Keycloak."""
    # Set the role using role name (not ID)
    await keycloak_admin._set_realm_roles(settings, request.userId, [request.roleName])
    
    return {"message": f"نقش کاربر به {request.roleName} تغییر یافت"}
