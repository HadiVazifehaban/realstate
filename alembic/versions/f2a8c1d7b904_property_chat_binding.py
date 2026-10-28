"""Bind internal properties and conversations to Keycloak subjects."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "f2a8c1d7b904"
down_revision: str | None = "e7c3b9a4216f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("property", sa.Column("owner_subject", sa.String(length=255), nullable=True))
    op.create_index("ix_property_owner_subject", "property", ["owner_subject"])
    op.add_column("chat_conversation", sa.Column("property_id", sa.Uuid(), nullable=True))
    op.add_column("chat_conversation", sa.Column("requester_subject", sa.String(length=255), nullable=True))
    op.add_column("chat_conversation", sa.Column("owner_subject", sa.String(length=255), nullable=True))
    op.create_foreign_key(None, "chat_conversation", "property", ["property_id"], ["id"])
    op.create_index("ix_chat_conversation_property_id", "chat_conversation", ["property_id"])
    op.create_index("ix_chat_conversation_requester_subject", "chat_conversation", ["requester_subject"])
    op.create_index("ix_chat_conversation_owner_subject", "chat_conversation", ["owner_subject"])
    # Existing generic chat rooms have no listing context and remain usable in
    # the existing messenger; only the new property-conversation route requires
    # these fields. PostgreSQL unique constraints allow NULL legacy rows.
    op.create_unique_constraint(
        "uq_chat_property_participants", "chat_conversation",
        ["property_id", "tenant_id", "requester_subject", "owner_subject"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    active_property_chats = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM chat_conversation WHERE property_id IS NOT NULL)"
    )).scalar()
    if active_property_chats:
        raise RuntimeError("Cannot downgrade while property-linked conversations exist.")
    op.drop_constraint("uq_chat_property_participants", "chat_conversation", type_="unique")
    op.drop_index("ix_chat_conversation_owner_subject", table_name="chat_conversation")
    op.drop_index("ix_chat_conversation_requester_subject", table_name="chat_conversation")
    op.drop_index("ix_chat_conversation_property_id", table_name="chat_conversation")
    op.drop_constraint("chat_conversation_property_id_fkey", "chat_conversation", type_="foreignkey")
    op.drop_column("chat_conversation", "owner_subject")
    op.drop_column("chat_conversation", "requester_subject")
    op.drop_column("chat_conversation", "property_id")
    op.drop_index("ix_property_owner_subject", table_name="property")
    op.drop_column("property", "owner_subject")
