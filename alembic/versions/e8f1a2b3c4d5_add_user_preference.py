"""Add ``user_preference`` table (per-user UI settings, e.g. active city).

Revision ID: e8f1a2b3c4d5
Revises: c9f3a1b7d2e6
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "e8f1a2b3c4d5"
down_revision = "c9f3a1b7d2e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_preference",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=256), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_preference_subject", "user_preference", ["subject"])
    op.create_index("ix_user_preference_key", "user_preference", ["key"])


def downgrade() -> None:
    op.drop_index("ix_user_preference_key", table_name="user_preference")
    op.drop_index("ix_user_preference_subject", table_name="user_preference")
    op.drop_table("user_preference")
