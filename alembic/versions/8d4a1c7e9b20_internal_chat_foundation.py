"""Internal, tenant-scoped messaging tables.

Revision ID: 8d4a1c7e9b20
Revises: a7c2d9e4f610
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8d4a1c7e9b20"
down_revision: Union[str, None] = "a7c2d9e4f610"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_conversation",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("created_by_subject", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(title) <= 160", name="ck_chat_conversation_title_length"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_chat_conversation_id_tenant"),
    )
    op.create_index("ix_chat_conversation_tenant_id", "chat_conversation", ["tenant_id"])

    op.create_table(
        "chat_membership",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("user_subject", sa.String(255), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversation.id"]),
        sa.ForeignKeyConstraint(
            ["conversation_id", "tenant_id"],
            ["chat_conversation.id", "chat_conversation.tenant_id"],
            name="fk_chat_member_conversation_tenant",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "user_subject", name="uq_chat_member_subject"),
        sa.UniqueConstraint(
            "conversation_id", "tenant_id", "user_subject",
            name="uq_chat_member_tenant_subject",
        ),
    )
    op.create_index("ix_chat_membership_conversation_id", "chat_membership", ["conversation_id"])
    op.create_index("ix_chat_membership_tenant_id", "chat_membership", ["tenant_id"])
    op.create_index("ix_chat_membership_user_subject", "chat_membership", ["user_subject"])

    op.create_table(
        "chat_message",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("sender_subject", sa.String(255), nullable=False),
        sa.Column("sender_name", sa.String(255), nullable=False),
        sa.Column("client_message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversation.id"]),
        sa.ForeignKeyConstraint(
            ["conversation_id", "tenant_id"],
            ["chat_conversation.id", "chat_conversation.tenant_id"],
            name="fk_chat_message_conversation_tenant",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id", "sender_subject", "client_message_id",
            name="uq_chat_message_idempotency",
        ),
        sa.UniqueConstraint("conversation_id", "sequence", name="uq_chat_message_sequence"),
        sa.UniqueConstraint(
            "conversation_id", "tenant_id", "id", name="uq_chat_message_tenant_id"
        ),
        sa.CheckConstraint("sequence >= 1", name="ck_chat_message_sequence"),
        sa.CheckConstraint("length(body) BETWEEN 1 AND 4000", name="ck_chat_message_body_length"),
    )
    op.create_index("ix_chat_message_conversation_id", "chat_message", ["conversation_id"])
    op.create_index("ix_chat_message_tenant_id", "chat_message", ["tenant_id"])
    op.create_index("ix_chat_message_sender_subject", "chat_message", ["sender_subject"])
    op.create_index("ix_chat_message_created_at", "chat_message", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_chat_message_created_at", table_name="chat_message")
    op.drop_index("ix_chat_message_sender_subject", table_name="chat_message")
    op.drop_index("ix_chat_message_tenant_id", table_name="chat_message")
    op.drop_index("ix_chat_message_conversation_id", table_name="chat_message")
    op.drop_table("chat_message")
    op.drop_index("ix_chat_membership_user_subject", table_name="chat_membership")
    op.drop_index("ix_chat_membership_tenant_id", table_name="chat_membership")
    op.drop_index("ix_chat_membership_conversation_id", table_name="chat_membership")
    op.drop_table("chat_membership")
    op.drop_index("ix_chat_conversation_tenant_id", table_name="chat_conversation")
    op.drop_table("chat_conversation")