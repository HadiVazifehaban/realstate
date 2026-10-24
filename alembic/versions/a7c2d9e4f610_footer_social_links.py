"""Add configurable footer social links (no fabricated destination seeds)."""

import sqlalchemy as sa
from alembic import op

revision = "a7c2d9e4f610"
down_revision = "f3a9c1d7e2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "footer_social_link",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("platform_key", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("icon_name", sa.String(64), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("sort_order >= 0", name="ck_footer_social_sort_order"),
    )
    op.create_index(
        "ix_footer_social_active_order", "footer_social_link", ["is_active", "sort_order"]
    )


def downgrade() -> None:
    op.drop_index("ix_footer_social_active_order", table_name="footer_social_link")
    op.drop_table("footer_social_link")