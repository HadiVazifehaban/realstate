"""add inter-agency collaboration tables (phases 2-5)

Revision ID: c9f3a1b7d2e6
Revises: a7b3c9d2e1f4
Create Date: 2026-10-14

Everything that happens *inside* a cooperation once two offices actually share
a file: listing shares with their permission matrix, lead referrals, the
append-only transfer history, the commission ledger (agreement + allocation +
payment), disputes with their message thread, and the audit trail that records
every security-sensitive cross-office action.

The three operational distinctions the spec insists on are structural here, not
convention: a share, a transfer and a referral are separate tables; ownership
history only ever appends; and every endpoint writes an audit row.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9f3a1b7d2e6"
down_revision: str | None = "a7b3c9d2e1f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Same rationale as the Phase 1 migration: the model also declares these enums,
# so ``op.create_table`` would emit a duplicate ``CREATE TYPE``. Each is created
# by hand inside an idempotent DO block so the migration stays re-runnable.
_ENUMS: dict[str, tuple[str, ...]] = {
    "share_mode": ("SHARE", "REFERRAL", "TRANSFER"),
    "share_status": ("ACTIVE", "EXPIRED", "REVOKED", "PENDING"),
    "referral_status": (
        "SENT", "VIEWED", "ACCEPTED", "IN_FOLLOW_UP",
        "CONVERTED", "LOST", "CANCELLED",
    ),
    "transfer_status": ("PENDING", "COMPLETED", "REJECTED", "CANCELLED"),
    "commission_model": ("PERCENTAGE", "FIXED"),
    "commission_status": ("DRAFT", "LOCKED", "PARTIALLY_PAID", "SETTLED", "DISPUTED"),
    "dispute_category": (
        "COMMISSION_MISMATCH", "OWNERSHIP", "UNAUTHORIZED_CONTACT",
        "UNAUTHORIZED_RESHARE", "CLIENT_OWNERSHIP", "SETTLEMENT_DELAY",
        "POLICY_VIOLATION",
    ),
    "dispute_status": (
        "OPEN", "UNDER_REVIEW", "WAITING_RESPONSE",
        "RESOLVED", "REJECTED", "ESCALATED",
    ),
    "audit_action": (
        "OWNER_PHONE_REVEALED", "ADDRESS_REVEALED", "LISTING_EXPORTED",
        "PERMISSION_CHANGED", "SHARE_CREATED", "SHARE_REVOKED", "SHARE_EXTENDED",
        "TRANSFER_EXECUTED", "COMMISSION_MODIFIED", "COMMISSION_LOCKED",
        "PAYMENT_RECORDED", "DISPUTE_OPENED", "DISPUTE_RESOLVED",
    ),
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*_ENUMS[name], name=name, create_type=False)


def _create_enums() -> None:
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
        "listing_share",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("property_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("source_agency_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("target_agency_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("mode", _enum("share_mode"), nullable=False, server_default="SHARE"),
        sa.Column("status", _enum("share_status"), nullable=False, server_default="ACTIVE"),
        sa.Column("target_agent", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("note", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("internal_note", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("revoked_by", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_listing_share_property_id", "listing_share", ["property_id"])
    op.create_index("ix_listing_share_source", "listing_share", ["source_agency_id"])
    op.create_index("ix_listing_share_target", "listing_share", ["target_agency_id"])

    # The permission matrix: every sensitive switch defaults OFF, so a share
    # created without an explicit grant stays on the safe end (Section F).
    op.create_table(
        "listing_share_permission",
        sa.Column("share_id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("view_summary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("view_full_details", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("show_owner_phone", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("show_exact_address", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_notes", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_visit_request", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_negotiation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_export", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_re_share", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=False, server_default=""),
    )

    op.create_table(
        "lead_referral",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("client_masked", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("source_agency_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("target_agency_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("property_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("assigned_to", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("referral_fee_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stage", _enum("referral_status"), nullable=False, server_default="SENT"),
        sa.Column("note", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("outcome", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_lead_referral_source", "lead_referral", ["source_agency_id"])
    op.create_index("ix_lead_referral_target", "lead_referral", ["target_agency_id"])

    # Append-only chain of custody for a file's responsibility.
    op.create_table(
        "listing_transfer_history",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("property_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("from_agency_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("to_agency_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("from_user", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("to_user", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("status", _enum("transfer_status"), nullable=False, server_default="PENDING"),
        sa.Column("reason", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("residual_commission_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("executed_by", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_listing_transfer_property_id", "listing_transfer_history", ["property_id"])
    op.create_index("ix_listing_transfer_from", "listing_transfer_history", ["from_agency_id"])
    op.create_index("ix_listing_transfer_to", "listing_transfer_history", ["to_agency_id"])

    op.create_table(
        "commission_agreement",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("property_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("source_agency_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("target_agency_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("model", _enum("commission_model"), nullable=False, server_default="PERCENTAGE"),
        sa.Column("status", _enum("commission_status"), nullable=False, server_default="DRAFT"),
        sa.Column("basis_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="IRR"),
        sa.Column("note", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("locked_by", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_commission_agreement_source", "commission_agreement", ["source_agency_id"])
    op.create_index("ix_commission_agreement_target", "commission_agreement", ["target_agency_id"])

    op.create_table(
        "commission_allocation",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("agreement_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("agency_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("agent", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fixed_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_commission_allocation_agreement", "commission_allocation", ["agreement_id"])

    op.create_table(
        "commission_payment",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("allocation_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("note", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("recorded_by", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_commission_payment_allocation", "commission_payment", ["allocation_id"])

    op.create_table(
        "dispute_case",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("category", _enum("dispute_category"), nullable=False),
        sa.Column("status", _enum("dispute_status"), nullable=False, server_default="OPEN"),
        sa.Column("claimant_agency_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("respondent_agency_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("share_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("agreement_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("referral_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("property_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("detail", sa.String(length=4000), nullable=False, server_default=""),
        sa.Column("resolution", sa.String(length=4000), nullable=False, server_default=""),
        sa.Column("opened_by", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("resolved_by", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_dispute_case_claimant", "dispute_case", ["claimant_agency_id"])
    op.create_index("ix_dispute_case_respondent", "dispute_case", ["respondent_agency_id"])

    op.create_table(
        "dispute_message",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("dispute_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("body", sa.String(length=4000), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_dispute_message_dispute", "dispute_message", ["dispute_id"])

    op.create_table(
        "network_audit_event",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("action", _enum("audit_action"), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("actor_agency_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("entity_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("property_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("target_agency_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("detail", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("network_audit_event")
    op.drop_index("ix_dispute_message_dispute", table_name="dispute_message")
    op.drop_table("dispute_message")
    op.drop_index("ix_dispute_case_respondent", table_name="dispute_case")
    op.drop_index("ix_dispute_case_claimant", table_name="dispute_case")
    op.drop_table("dispute_case")
    op.drop_index("ix_commission_payment_allocation", table_name="commission_payment")
    op.drop_table("commission_payment")
    op.drop_index("ix_commission_allocation_agreement", table_name="commission_allocation")
    op.drop_table("commission_allocation")
    op.drop_index("ix_commission_agreement_target", table_name="commission_agreement")
    op.drop_index("ix_commission_agreement_source", table_name="commission_agreement")
    op.drop_table("commission_agreement")
    op.drop_index("ix_listing_transfer_to", table_name="listing_transfer_history")
    op.drop_index("ix_listing_transfer_from", table_name="listing_transfer_history")
    op.drop_index("ix_listing_transfer_property_id", table_name="listing_transfer_history")
    op.drop_table("listing_transfer_history")
    op.drop_index("ix_lead_referral_target", table_name="lead_referral")
    op.drop_index("ix_lead_referral_source", table_name="lead_referral")
    op.drop_table("lead_referral")
    op.drop_table("listing_share_permission")
    op.drop_index("ix_listing_share_target", table_name="listing_share")
    op.drop_index("ix_listing_share_source", table_name="listing_share")
    op.drop_index("ix_listing_share_property_id", table_name="listing_share")
    op.drop_table("listing_share")
    _drop_enums()
