"""add agency network tables

Revision ID: a7b3c9d2e1f4
Revises: d6a1c4f8b2e3
Create Date: 2026-10-13

Phase 1 of the inter-agency collaboration network: offices exist as rows, and
a cooperation agreement is what lets two of them work a file together. Sharing,
transfers, referrals, commissions and disputes are later phases, so this
migration intentionally creates only the two tables those need.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7b3c9d2e1f4"
down_revision: str | None = "d6a1c4f8b2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# The enums live in the model too, and `op.create_table` emits a ``CREATE TYPE``
# for an enum it finds on a column. Creating one here as well therefore fails
# with "already exists", so the DDL is issued by hand in a DO block that
# swallows the duplicate -- which also makes the migration re-runnable, the
# alternative being a migration that can only ever be applied to an empty DB.
_ENUMS: dict[str, tuple[str, ...]] = {
    "agency_status": ("PENDING", "VERIFIED", "SUSPENDED"),
    "cooperation_status": ("PENDING", "APPROVED", "REJECTED", "COUNTER", "REVOKED"),
    "cooperation_scope": ("SHARE_LISTINGS", "REFER_LEADS", "CO_BROKE", "FULL_MERGE"),
}

agency_status = postgresql.ENUM(
    "PENDING", "VERIFIED", "SUSPENDED",
    name="agency_status", create_type=False,
)
cooperation_status = postgresql.ENUM(
    "PENDING", "APPROVED", "REJECTED", "COUNTER", "REVOKED",
    name="cooperation_status", create_type=False,
)
cooperation_scope = postgresql.ENUM(
    "SHARE_LISTINGS", "REFER_LEADS", "CO_BROKE", "FULL_MERGE",
    name="cooperation_scope", create_type=False,
)


def _create_enums() -> None:
    """Create the collaboration enums if this database does not have them."""
    bind = op.get_bind()
    for name, members in _ENUMS.items():
        values = ", ".join(f"'{member}'" for member in members)
        bind.execute(
            sa.text(
                f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_type t
                        JOIN pg_namespace n ON n.oid = t.typnamespace
                        WHERE t.typname = '{name}'
                    ) THEN
                        CREATE TYPE {name} AS ENUM ({values});
                    END IF;
                END $$;
                """
            )
        )


def _drop_enums() -> None:
    bind = op.get_bind()
    for name in _ENUMS:
        exists = (
            bind.execute(
                sa.text(
                    "SELECT 1 FROM pg_type t "
                    "JOIN pg_namespace n ON n.oid = t.typnamespace "
                    "WHERE t.typname = :name"
                ),
                {"name": name},
            )
            .first()
            is not None
        )
        if exists:
            bind.execute(sa.text(f"DROP TYPE {name}"))


def upgrade() -> None:
    _create_enums()
    op.create_table(
        "agency",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("name_fa", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("city", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("district", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("phone", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("logo_url", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("description", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("status", agency_status, nullable=False, server_default="PENDING"),
        sa.Column("verified_by", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("settlement_iban", sa.String(length=34), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agency_slug", "agency", ["slug"], unique=True)

    op.create_table(
        "agency_cooperation",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("requester_agency_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("target_agency_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("status", cooperation_status, nullable=False, server_default="PENDING"),
        sa.Column("scope", cooperation_scope, nullable=False, server_default="SHARE_LISTINGS"),
        sa.Column("granted_scopes", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("default_commission_pct", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("requested_by", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("decided_by", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_agency_cooperation_requester", "agency_cooperation", ["requester_agency_id"]
    )
    op.create_index(
        "ix_agency_cooperation_target", "agency_cooperation", ["target_agency_id"]
    )


def downgrade() -> None:
    op.drop_table("agency_cooperation")
    op.drop_table("agency")
    _drop_enums()
