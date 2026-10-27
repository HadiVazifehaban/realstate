"""Database-authoritative Keycloak subject to agency memberships.

Revision ID: 4c2a7d9e1f30
Revises: 8d4a1c7e9b20

No existing agency users or token tenant claims are backfilled: neither is
authoritative evidence that a Keycloak subject owns an agency membership.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4c2a7d9e1f30"
down_revision: str | None = "0a8b5dea0d94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agency_membership",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("agency_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_subject", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=64), server_default="MEMBER", nullable=False),
        sa.Column("created_by_subject", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_subject", sa.String(length=255), server_default="", nullable=False),
        sa.CheckConstraint(
            "length(user_subject) BETWEEN 1 AND 255",
            name="ck_agency_membership_subject_length",
        ),
        sa.CheckConstraint(
            "length(role) BETWEEN 1 AND 64",
            name="ck_agency_membership_role_length",
        ),
        sa.ForeignKeyConstraint(["agency_id"], ["agency.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "agency_id", "user_subject", name="uq_agency_membership_agency_subject"
        ),
    )
    op.create_index("ix_agency_membership_agency_id", "agency_membership", ["agency_id"])
    op.create_index("ix_agency_membership_user_subject", "agency_membership", ["user_subject"])
    op.create_index(
        "ix_agency_membership_active_subject",
        "agency_membership",
        ["user_subject", "agency_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_agency_membership_active_subject", table_name="agency_membership")
    op.drop_index("ix_agency_membership_user_subject", table_name="agency_membership")
    op.drop_index("ix_agency_membership_agency_id", table_name="agency_membership")
    op.drop_table("agency_membership")