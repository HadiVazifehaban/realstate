"""Phase 5: CRM pipeline, PII reveal quota and the role/source vocabulary.

Revision ID: e2f4a6b8c9d1
Revises: d5e8f2a1b7c4

Adds the broker desk's persistence layer:

* ``crm_lead`` — one card per property on the five-column board, with the
  property's valuation verdict denormalised so the board can sort on bargain
  without a join;
* ``lead_interaction`` — the append-only timeline. A visit appointment is a
  ``VISIT_EVENT`` row carrying ``scheduled_at``; there is deliberately **no**
  ``visit_date`` column on any table;
* ``pii_quota`` — per-user daily reveal counter, unique on ``(user_id, day)``
  so a second reveal updates the row instead of silently resetting the cap.

``property_source`` and ``property_status`` are swapped rather than created, so
a directly registered owner listing can outrank a scraped one and a withdrawn
unit stays distinguishable from an archived deal.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e2f4a6b8c9d1"
down_revision: Union[str, None] = "d5e8f2a1b7c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ROLE_LABELS = (
    "GUEST", "USER", "OWNER", "AGENT",
    "OFFICE_MANAGER", "SUPERVISOR", "ADMIN",
)
LEAD_STAGE_LABELS = (
    "NEW_FILE", "CONTACTING", "APPRAISAL",
    "CONTRACT_READY", "CLOSED_DEAL", "LOST_ARCHIVED",
)
LEAD_PRIORITY_LABELS = ("URGENT_BARGAIN", "HIGH", "NORMAL", "LOW")
INTERACTION_LABELS = (
    "PHONE_CALL", "VISIT_EVENT", "NOTE_ADDED", "PRICE_OFFER", "STAGE_CHANGED",
)
TIER_LABELS = ("FREE", "BASIC", "PRO", "ENTERPRISE")
SOURCE_LABELS = (
    "INTERNAL_USER", "INTERNAL_AGENCY", "SHEYPOOR", "DIVAR", "MLS_IMPORT",
    "DIVAR_KENAR", "DIVAR_SCRAPER", "MANUAL_OFFICE",
)
STATUS_LABELS = (
    "DRAFT", "ACTIVE", "RESERVED", "SOLD", "RENTED", "WITHDRAWN", "ARCHIVED",
)


def _enum(labels: tuple[str, ...], name: str) -> postgresql.ENUM:
    """Create the PG enum up-front so a partial run stays replayable."""
    enum = postgresql.ENUM(*labels, name=name)
    enum.create(op.get_bind(), checkfirst=True)
    return postgresql.ENUM(*labels, name=name, create_type=False)


#: Maps each enum type onto the property column that stores it. The column names
#: do not mirror the type names (``source`` holds ``property_source``), so this
#: is explicit rather than derived.
ENUM_COLUMNS = {"property_source": "source", "property_status": "status"}


def _swap_enum(enum_name: str, labels: tuple[str, ...]) -> None:
    """Recreate an existing native enum, migrating the rows across.

    PostgreSQL cannot add values to an enum inside a transaction, so the type is
    renamed out of the way, recreated with the new shape, and every column is
    cast over. Existing rows keep their value as long as the label survives.

    The rename target is dropped first: a previous partial run may have left a
    `_old` type behind, and `ALTER TYPE ... RENAME` fails outright if the
    destination name is taken.
    """
    bind = op.get_bind()
    column = ENUM_COLUMNS[enum_name]
    old_name = f"{enum_name}_old"

    # A partial run may have left the current type already renamed out of the way.
    exists = bind.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :name"), {"name": enum_name}
    ).first()
    already_swapped = exists is None

    postgresql.ENUM(name=old_name).drop(bind, checkfirst=True)
    if not already_swapped:
        op.execute(f'ALTER TYPE {enum_name} RENAME TO "{old_name}"')
    postgresql.ENUM(*labels, name=enum_name).create(bind, checkfirst=True)
    op.execute(
        f"ALTER TABLE property ALTER COLUMN {column} "
        f"TYPE {enum_name} USING {column}::text::{enum_name}"
    )
    postgresql.ENUM(name=old_name).drop(bind, checkfirst=True)


def upgrade() -> None:
    _enum(ROLE_LABELS, "user_role")
    _enum(LEAD_STAGE_LABELS, "lead_stage")
    _enum(LEAD_PRIORITY_LABELS, "lead_priority")
    _enum(INTERACTION_LABELS, "interaction_type")
    _enum(TIER_LABELS, "saas_tier")

    _swap_enum("property_source", SOURCE_LABELS)
    _swap_enum("property_status", STATUS_LABELS)

    op.create_table(
        "crm_lead",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("property_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "stage",
            postgresql.ENUM(*LEAD_STAGE_LABELS, name="lead_stage", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "priority",
            postgresql.ENUM(
                *LEAD_PRIORITY_LABELS, name="lead_priority", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_bargain", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("deviation_pct", sa.Float(), nullable=True),
        sa.Column(
            "neighborhood", sa.String(length=128), nullable=False, server_default=""
        ),
        sa.Column("city", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["property.id"]),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["agency_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_lead_stage", "crm_lead", ["stage"])
    op.create_index("ix_crm_lead_property_id", "crm_lead", ["property_id"])
    op.create_index("ix_crm_lead_is_bargain", "crm_lead", ["is_bargain"])

    op.create_table(
        "lead_interaction",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "interaction_type",
            postgresql.ENUM(
                *INTERACTION_LABELS, name="interaction_type", create_type=False
            ),
            nullable=False,
        ),
        # The single home for an appointment time, deliberately named
        # `scheduled_at`: a property never carries a visit date.
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["crm_lead.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["agency_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_interaction_lead_id", "lead_interaction", ["lead_id"])
    op.create_index(
        "ix_lead_interaction_scheduled_at", "lead_interaction", ["scheduled_at"]
    )

    op.create_table(
        "pii_quota",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column(
            "tier",
            postgresql.ENUM(*TIER_LABELS, name="saas_tier", create_type=False),
            nullable=False,
        ),
        sa.Column("consumed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["agency_user.id"]),
        sa.PrimaryKeyConstraint("id"),
        # Without this, a second reveal would insert a fresh row and the tier
        # cap would silently reset.
        sa.UniqueConstraint("user_id", "day", name="uq_pii_quota_user_day"),
    )
    op.create_index("ix_pii_quota_user_id", "pii_quota", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_pii_quota_user_id", table_name="pii_quota")
    op.drop_table("pii_quota")
    op.drop_index(
        "ix_lead_interaction_scheduled_at", table_name="lead_interaction"
    )
    op.drop_index("ix_lead_interaction_lead_id", table_name="lead_interaction")
    op.drop_table("lead_interaction")
    op.drop_index("ix_crm_lead_is_bargain", table_name="crm_lead")
    op.drop_index("ix_crm_lead_property_id", table_name="crm_lead")
    op.drop_index("ix_crm_lead_stage", table_name="crm_lead")
    op.drop_table("crm_lead")

    bind = op.get_bind()
    for name in (
        "saas_tier",
        "interaction_type",
        "lead_priority",
        "lead_stage",
        "user_role",
    ):
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)

