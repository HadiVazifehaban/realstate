"""User directory schemas (agency staff), shaped for the dashboard table."""

from __future__ import annotations

import uuid
from datetime import datetime

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
    role: UserRole = UserRole.AGENT
    status: str = "ACTIVE"


__all__ = [
    "RoleBreakdownItem",
    "UserMutationIn",
    "UserOut",
    "UsersListResponse",
]
