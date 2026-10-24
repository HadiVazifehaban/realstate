"""Phase 3: property_match table (scored property <-> client demand links).

Revision ID: f7a2b91c4d60
Revises: c4e19a7d2f83

Phase 1 shipped the deterministic scoring helpers and the ``client_demand``
model but no place to persist the results. This adds:

* the ``match_status`` enum
* the ``property_match`` table, unique on ``(property_id, demand_id)`` so a
  re-scrape updates the existing score instead of duplicating the suggestion
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f7a2b91c4d60"
down_revision: Union[str, None] = "c4e19a7d2f83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    _MATCH_STATUS_LABELS = ("NEW", "SEEN", "SHORTLISTED", "DISMISSED", "CONTACTED")
    match_status = postgresql.ENUM(
        *_MATCH_STATUS_LABELS, name="match_status"
    )
    # Created explicitly first; ``checkfirst`` makes a partially-applied run
    # (enum created, table not) replayable.
    match_status.create(op.get_bind(), checkfirst=True)
    # Referenced with create_type=False so create_table does not emit a second
    # CREATE TYPE in the same transaction (that is a DuplicateObject error).
    match_status_col = postgresql.ENUM(
        *_MATCH_STATUS_LABELS, name="match_status", create_type=False
    )

    op.create_table(
        "property_match",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("property_id", sa.Uuid(), nullable=False),
        sa.Column("demand_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("geo_score", sa.Float(), nullable=False),
        sa.Column("price_score", sa.Float(), nullable=False),
        sa.Column("specs_score", sa.Float(), nullable=False),
        sa.Column(
            "breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", match_status_col, nullable=False),
        sa.Column("distance_meters", sa.Float(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["property_id"], ["property.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["demand_id"], ["client_demand.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # One suggestion per (listing, demand): re-scoring updates in place.
        sa.UniqueConstraint("property_id", "demand_id", name="uq_property_match_pair"),
    )
    op.create_index(
        op.f("ix_property_match_property_id"), "property_match", ["property_id"]
    )
    op.create_index(
        op.f("ix_property_match_demand_id"), "property_match", ["demand_id"]
    )
    op.create_index(op.f("ix_property_match_status"), "property_match", ["status"])
    op.create_index(
        op.f("ix_property_match_created_at"), "property_match", ["created_at"]
    )
    # The agent's main view: newest best-scoring suggestions first.
    op.create_index(
        "ix_property_match_demand_score",
        "property_match",
        ["demand_id", "score"],
    )


def downgrade() -> None:
    op.drop_index("ix_property_match_demand_score", table_name="property_match")
    op.drop_index(op.f("ix_property_match_created_at"), table_name="property_match")
    op.drop_index(op.f("ix_property_match_status"), table_name="property_match")
    op.drop_index(op.f("ix_property_match_demand_id"), table_name="property_match")
    op.drop_index(op.f("ix_property_match_property_id"), table_name="property_match")
    op.drop_table("property_match")
    postgresql.ENUM(name="match_status").drop(op.get_bind(), checkfirst=True)