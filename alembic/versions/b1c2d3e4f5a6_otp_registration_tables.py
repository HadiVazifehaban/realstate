"""OTP registration tables: professional applications + auth audit log.

Revision ID: b1c2d3e4f5a6
Revises: e8f1a2b3c4d5
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "e8f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "professional_application",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mobile", sa.String(length=16), nullable=False),
        sa.Column("keycloak_user_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("requested_role", sa.String(length=64), nullable=False),
        sa.Column("assigned_role", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("first_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("last_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="ROLE_REVIEW_PENDING",
        ),
        sa.Column("reviewer_note", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("reviewed_by", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_professional_application_mobile",
        "professional_application",
        ["mobile"],
    )
    op.create_index(
        "ix_professional_application_status",
        "professional_application",
        ["status"],
    )

    op.create_table(
        "auth_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("masked_mobile", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("keycloak_user_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("outcome", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("detail", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("client_ip", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_audit_log_event", "auth_audit_log", ["event"])


def downgrade() -> None:
    op.drop_index("ix_auth_audit_log_event", table_name="auth_audit_log")
    op.drop_table("auth_audit_log")
    op.drop_index("ix_professional_application_status", table_name="professional_application")
    op.drop_index("ix_professional_application_mobile", table_name="professional_application")
    op.drop_table("professional_application")
