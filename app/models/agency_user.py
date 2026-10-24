"""Agency users (advisors/managers) and their roles."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import SQLModel, Field, Column

from app.models.base import pg_enum, timestamp_column, utcnow, uuid_column
from app.models.enums import UserRole

_RoleCol = Column(pg_enum(UserRole, "user_role"), nullable=False, default=UserRole.AGENT)


class AgencyUser(SQLModel, table=True):
    """A staff member of the real-estate agency."""

    __tablename__ = "agency_user"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    username: str = Field(index=True, unique=True, max_length=64)
    full_name: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=32)
    password_hash: str = Field(default="", max_length=512)
    role: UserRole = Field(default=UserRole.AGENT, sa_column=_RoleCol)
    is_active: bool = Field(default=True)

    # Placeholder for future multi-branch support; the local node has one agency.
    agency_id: str = Field(default="local", max_length=128)

    last_login_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())

    @property
    def is_manager(self) -> bool:
        """True for roles that can run the office, not just work leads."""
        return self.role in (
            UserRole.OFFICE_MANAGER,
            UserRole.SUPERVISOR,
            UserRole.ADMIN,
        )
