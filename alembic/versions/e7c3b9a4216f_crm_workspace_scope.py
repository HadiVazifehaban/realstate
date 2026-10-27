"""Scope CRM lead cards and owner-PII audit records to a workspace."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "e7c3b9a4216f"
down_revision: str | None = "d9b41e7a2c63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("crm_lead", sa.Column("agency_id", sa.String(length=64), nullable=True))
    op.add_column("crm_lead", sa.Column("assigned_subject", sa.String(length=255), nullable=True))
    # Preserve existing single-office CRM records in a named legacy scope and
    # prefer the canonical agency owner when the linked Property has one.
    op.execute(sa.text(
        "UPDATE crm_lead AS l SET agency_id = COALESCE(CAST(p.agency_id AS VARCHAR(64)), 'local') "
        "FROM property AS p WHERE p.id = l.property_id AND l.agency_id IS NULL"
    ))
    op.execute(sa.text("UPDATE crm_lead SET agency_id = 'local' WHERE agency_id IS NULL"))
    op.alter_column(
        "crm_lead", "agency_id", existing_type=sa.String(length=64),
        nullable=False, server_default="local",
    )
    op.create_index("ix_crm_lead_agency_id", "crm_lead", ["agency_id"])
    op.create_index("ix_crm_lead_assigned_subject", "crm_lead", ["assigned_subject"])
    op.create_index("ix_crm_lead_agency_stage_updated", "crm_lead", ["agency_id", "stage", "updated_at"])

    op.add_column("owner_access_log", sa.Column("agency_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(None, "owner_access_log", "agency", ["agency_id"], ["id"])
    op.create_index("ix_owner_access_log_agency_id", "owner_access_log", ["agency_id"])
    op.execute(sa.text(
        "UPDATE owner_access_log AS a SET agency_id = p.agency_id "
        "FROM property AS p WHERE p.id = a.property_id AND a.agency_id IS NULL AND p.agency_id IS NOT NULL"
    ))


def downgrade() -> None:
    bind = op.get_bind()
    has_scoped_leads = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM crm_lead WHERE agency_id <> 'local' OR assigned_subject IS NOT NULL)"
    )).scalar()
    has_scoped_audits = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM owner_access_log WHERE agency_id IS NOT NULL)"
    )).scalar()
    if has_scoped_leads or has_scoped_audits:
        raise RuntimeError("Cannot downgrade while workspace-scoped CRM or owner-PII audit data exists.")

    op.drop_index("ix_owner_access_log_agency_id", table_name="owner_access_log")
    op.drop_constraint("owner_access_log_agency_id_fkey", "owner_access_log", type_="foreignkey")
    op.drop_column("owner_access_log", "agency_id")
    op.drop_index("ix_crm_lead_agency_stage_updated", table_name="crm_lead")
    op.drop_index("ix_crm_lead_assigned_subject", table_name="crm_lead")
    op.drop_index("ix_crm_lead_agency_id", table_name="crm_lead")
    op.drop_column("crm_lead", "assigned_subject")
    op.drop_column("crm_lead", "agency_id")
