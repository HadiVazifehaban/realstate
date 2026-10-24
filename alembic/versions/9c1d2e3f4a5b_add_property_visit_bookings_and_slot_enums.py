"""Add property_visit_bookings table and visit slot enums

Revision ID: 9c1d2e3f4a5b
Revises: c4d8e1f2a905
Create Date: 2026-10-10 11:20:00.000000

The red-line rule prohibits `visit_date` on the listing row, so the calendar
schedule lives in its own table. This migration creates the
``property_visit_booking`` table plus the two PostgreSQL enums that back the
scheduler widget's availability chips: ``visit_slot_status`` and
``visit_slot_kind``.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9c1d2e3f4a5b"
# Based on the live head (``c4d8e1f2a905``), not on the shared branch point
# ``f1a2b3c4d5e6`` -- branching from the branch point leaves alembic with two
# heads and ``alembic upgrade head`` refuses to run.
down_revision: Union[str, None] = "c4d8e1f2a905"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    # --- 1) New enums (Postgres native types) ------------------------------
    # Created explicitly with ``checkfirst`` so a half-applied run can be
    # retried; the columns below then reference them with ``create_type=False``
    # so ``op.create_table`` does not issue a second CREATE TYPE for the same
    # name and aborts the whole migration.
    visit_slot_status = postgresql.ENUM(
        "DRAFT",
        "REQUESTED",
        "CONFIRMED",
        "CANCELLED",
        "NO_SHOW",
        "COMPLETED",
        name="visit_slot_status",
        create_type=False,
    )
    postgresql.ENUM(
        "DRAFT",
        "REQUESTED",
        "CONFIRMED",
        "CANCELLED",
        "NO_SHOW",
        "COMPLETED",
        name="visit_slot_status",
    ).create(op.get_bind(), checkfirst=True)

    visit_slot_kind = postgresql.ENUM(
        "OFFICE_HOUSE",
        "PHONE",
        "VIRTUAL",
        name="visit_slot_kind",
        create_type=False,
    )
    postgresql.ENUM(
        "OFFICE_HOUSE",
        "PHONE",
        "VIRTUAL",
        name="visit_slot_kind",
    ).create(op.get_bind(), checkfirst=True)

    # --- 2) New table ---------------------------------------------------
    op.create_table(
        "property_visit_booking",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("property_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("slot_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column(
            "status",
            visit_slot_status,
            nullable=False,
        ),
        sa.Column(
            "kind",
            visit_slot_kind,
            nullable=False,
        ),
        sa.Column("guests", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["property_id"], ["property.id"]
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["agency_user.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "property_id", "slot_date", "start_time",
            name="uq_property_visit_booking_slot",
        ),
    )

    # --- 3) Indexes ------------------------------------------------------
    op.create_index(
        op.f("ix_property_visit_booking_property_id"),
        "property_visit_booking",
        ["property_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_property_visit_booking_created_by_user_id"),
        "property_visit_booking",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_property_visit_booking_slot_date"),
        "property_visit_booking",
        ["slot_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_property_visit_booking_start_time"),
        "property_visit_booking",
        ["start_time"],
        unique=False,
    )
    op.create_index(
        op.f("ix_property_visit_booking_status"),
        "property_visit_booking",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_property_visit_booking_end_time"),
        "property_visit_booking",
        ["end_time"],
        unique=False,
    )


def downgrade() -> None:
    # --- 3) Drop indexes -----------------------------------------------
    op.drop_index(op.f("ix_property_visit_booking_end_time"),
                  table_name="property_visit_booking")
    op.drop_index(op.f("ix_property_visit_booking_status"),
                  table_name="property_visit_booking")
    op.drop_index(op.f("ix_property_visit_booking_start_time"),
                  table_name="property_visit_booking")
    op.drop_index(op.f("ix_property_visit_booking_slot_date"),
                  table_name="property_visit_booking")
    op.drop_index(op.f("ix_property_visit_booking_created_by_user_id"),
                  table_name="property_visit_booking")
    op.drop_index(op.f("ix_property_visit_booking_property_id"),
                  table_name="property_visit_booking")

    # --- 2) Drop table -------------------------------------------------
    op.drop_table("property_visit_booking")

    # --- 1) Drop enums ---------------------------------------------------
    with op.get_context().autocommit_block():
        op.execute("DROP TYPE IF EXISTS visit_slot_status")
        op.execute("DROP TYPE IF EXISTS visit_slot_kind")
