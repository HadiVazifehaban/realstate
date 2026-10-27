"""User directory schemas (agency staff), shaped for the dashboard table."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import UserRole


class UserOut(BaseModel):
    id: str
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    status: str = "ACTIVE"
    role: UserRole
    realm_roles: list[str] = Field(default_factory=list)
    kyc_status: str = "PENDING"
    mobile_verified: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RoleBreakdownItem(BaseModel):
    role: UserRole
    count: int


class UsersListResponse(BaseModel):
    success: bool = True
    time: str = ""
    message: str = ""
    total_users: int = 0
    offset: int = 0
    limit: int = 10
    users: list[UserOut] = Field(default_factory=list)
    role_breakdown: list[RoleBreakdownItem] = Field(default_factory=list)


class UserMutationIn(BaseModel):
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    role: UserRole | None = None
    # The internal AGENT tier alone cannot distinguish Junior from Senior.
    # Office-manager mutations are restricted to these two exact Realm roles.
    keycloak_role: Literal["ROLE_JUNIOR_BROKER", "ROLE_SENIOR_BROKER"] | None = None
    status: str | None = None


__all__ = [
    "RoleBreakdownItem",
    "UserMutationIn",
    "UserOut",
    "UsersListResponse",
]
