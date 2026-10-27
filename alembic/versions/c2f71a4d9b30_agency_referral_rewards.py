"""Agency referral codes and auditable one-time renewal credits.

Revision ID: c2f71a4d9b30
Revises: 4c2a7d9e1f30

Existing agencies receive random stable codes in batches. Existing payment and
subscription rows are not rewritten. Downgrade drops referral data and the
new code column; back up referral activity before intentionally rolling back.
"""

from __future__ import annotations

import secrets
import string
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c2f71a4d9b30"
down_revision: str | None = "4c2a7d9e1f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

referral_status = postgresql.ENUM("PENDING", "COMPLETED", "VOIDED", name="agency_referral_status", create_type=False)
credit_status = postgresql.ENUM("AVAILABLE", "PENDING", "RESERVED", "CONSUMED", "RELEASED", "VOIDED", name="referral_credit_status", create_type=False)
_ALPHABET = string.ascii_uppercase + string.digits


def _unique_codes(bind: sa.Connection, count: int) -> list[str]:
    codes: list[str] = []
    while len(codes) < count:
        candidate = "SH" + "".join(secrets.choice(_ALPHABET) for _ in range(10))
        exists = bind.execute(
            sa.text("SELECT 1 FROM agency WHERE referral_code = :code"), {"code": candidate}
        ).first()
        if candidate not in codes and exists is None:
            codes.append(candidate)
    return codes


def upgrade() -> None:
    bind = op.get_bind()
    referral_status.create(bind, checkfirst=True)
    credit_status.create(bind, checkfirst=True)

    op.add_column("payment_order", sa.Column("base_amount_toman", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("payment_order", sa.Column("discount_percent", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("payment_order", sa.Column("discount_amount_toman", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("payment_order", sa.Column("referral_credit_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("payment_order", sa.Column("referral_invoice_applied", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE payment_order SET base_amount_toman = amount_toman")

    op.add_column("agency", sa.Column("referral_code", sa.String(16), nullable=True))
    op.create_index("ix_agency_referral_code", "agency", ["referral_code"], unique=True)

    last_id = None
    while True:
        query = sa.text(
            "SELECT id FROM agency WHERE referral_code IS NULL "
            + ("AND id > :last_id " if last_id else "")
            + "ORDER BY id LIMIT 500"
        )
        params = {"last_id": last_id} if last_id else {}
        ids = [row[0] for row in bind.execute(query, params)]
        if not ids:
            break
        codes = _unique_codes(bind, len(ids))
        for agency_id, code in zip(ids, codes, strict=True):
            bind.execute(
                sa.text("UPDATE agency SET referral_code = :code WHERE id = :agency_id"),
                {"code": code, "agency_id": agency_id},
            )
        last_id = ids[-1]

    op.alter_column("agency", "referral_code", nullable=False, server_default="")

    op.create_table(
        "agency_referral",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("referrer_agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("referred_agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_used", sa.String(16), nullable=False),
        sa.Column("status", referral_status, nullable=False),
        sa.Column("source", sa.String(32), server_default="professional_registration", nullable=False),
        sa.Column("created_by_subject", sa.String(255), server_default="", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("referrer_agency_id <> referred_agency_id", name="ck_agency_referral_distinct_agencies"),
        sa.ForeignKeyConstraint(["referrer_agency_id"], ["agency.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["referred_agency_id"], ["agency.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["completion_order_id"], ["payment_order.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referred_agency_id", name="uq_agency_referral_referred"),
    )
    op.create_index("ix_agency_referral_referrer_agency_id", "agency_referral", ["referrer_agency_id"])
    op.create_index("ix_agency_referral_referred_agency_id", "agency_referral", ["referred_agency_id"])
    op.create_index("ix_agency_referral_completion_order_id", "agency_referral", ["completion_order_id"])
    op.create_index("ix_agency_referral_created_at", "agency_referral", ["created_at"])
    op.create_index("ix_agency_referral_referrer_status", "agency_referral", ["referrer_agency_id", "status"])

    op.create_table(
        "referral_credit",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("referral_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", credit_status, nullable=False),
        sa.Column("percent", sa.Integer(), nullable=False),
        sa.Column("reserved_order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("consumed_order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("percent > 0 AND percent <= 20", name="ck_referral_credit_percent"),
        sa.ForeignKeyConstraint(["agency_id"], ["agency.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["referral_id"], ["agency_referral.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reserved_order_id"], ["payment_order.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["consumed_order_id"], ["payment_order.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referral_id", name="uq_referral_credit_referral"),
    )
    op.create_index("ix_referral_credit_agency_id", "referral_credit", ["agency_id"])
    op.create_index("ix_referral_credit_referral_id", "referral_credit", ["referral_id"])
    op.create_index("ix_referral_credit_reserved_order_id", "referral_credit", ["reserved_order_id"])
    op.create_index("ix_referral_credit_consumed_order_id", "referral_credit", ["consumed_order_id"])
    op.create_index("ix_referral_credit_agency_status", "referral_credit", ["agency_id", "status"])


def downgrade() -> None:
    for index in (
        "ix_referral_credit_agency_status", "ix_referral_credit_consumed_order_id",
        "ix_referral_credit_reserved_order_id", "ix_referral_credit_referral_id",
        "ix_referral_credit_agency_id",
    ):
        op.drop_index(index, table_name="referral_credit")
    op.drop_table("referral_credit")
    for index in (
        "ix_agency_referral_referrer_status", "ix_agency_referral_created_at",
        "ix_agency_referral_completion_order_id", "ix_agency_referral_referred_agency_id",
        "ix_agency_referral_referrer_agency_id",
    ):
        op.drop_index(index, table_name="agency_referral")
    op.drop_table("agency_referral")
    op.drop_index("ix_agency_referral_code", table_name="agency")
    op.drop_column("agency", "referral_code")
    op.drop_column("payment_order", "referral_credit_count")
    op.drop_column("payment_order", "referral_invoice_applied")
    op.drop_column("payment_order", "discount_amount_toman")
    op.drop_column("payment_order", "discount_percent")
    op.drop_column("payment_order", "base_amount_toman")
    bind = op.get_bind()
    credit_status.drop(bind, checkfirst=True)
    referral_status.drop(bind, checkfirst=True)