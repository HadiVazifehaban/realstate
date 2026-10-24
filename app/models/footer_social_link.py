"""Site-wide, administrator-managed footer destinations."""

import uuid

from sqlalchemy import CheckConstraint, Index
from sqlmodel import Field, SQLModel

from app.models.base import uuid_column


class FooterSocialLink(SQLModel, table=True):
    __tablename__ = "footer_social_link"
    __table_args__ = (
        CheckConstraint("sort_order >= 0", name="ck_footer_social_sort_order"),
        Index("ix_footer_social_active_order", "is_active", "sort_order"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    platform_key: str = Field(max_length=64)
    display_name: str = Field(max_length=100)
    icon_name: str = Field(max_length=64)
    url: str = Field(max_length=2048)
    is_active: bool = Field(default=True, nullable=False)
    sort_order: int = Field(default=0, nullable=False)