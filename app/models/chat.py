"""Tenant-scoped internal messaging records.

This first slice deliberately supports internal conversations only. It does not
grant cross-agency access, attach business records, or store file payloads.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Column, ForeignKeyConstraint, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.base import timestamp_column, utcnow, uuid_column


class ChatConversation(SQLModel, table=True):
    __tablename__ = "chat_conversation"
    __table_args__ = (
        CheckConstraint("length(title) <= 160", name="ck_chat_conversation_title_length"),
        UniqueConstraint("id", "tenant_id", name="uq_chat_conversation_id_tenant"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    tenant_id: str = Field(index=True, max_length=255)
    title: str = Field(default="", max_length=160)
    created_by_subject: str = Field(max_length=255)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())

class ChatMembership(SQLModel, table=True):
    __tablename__ = "chat_membership"
    __table_args__ = (
        UniqueConstraint("conversation_id", "user_subject", name="uq_chat_member_subject"),
        UniqueConstraint("conversation_id", "tenant_id", "user_subject", name="uq_chat_member_tenant_subject"),
        # The composite FK prevents an application bug from attaching a member
        # row to a conversation belonging to another tenant.
        ForeignKeyConstraint(
            ["conversation_id", "tenant_id"],
            ["chat_conversation.id", "chat_conversation.tenant_id"],
            name="fk_chat_member_conversation_tenant",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    conversation_id: uuid.UUID = Field(foreign_key="chat_conversation.id", index=True)
    tenant_id: str = Field(index=True, max_length=255)
    user_subject: str = Field(index=True, max_length=255)
    joined_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    left_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_message"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "sender_subject", "client_message_id",
            name="uq_chat_message_idempotency",
        ),
        UniqueConstraint("conversation_id", "sequence", name="uq_chat_message_sequence"),
        UniqueConstraint("conversation_id", "tenant_id", "id", name="uq_chat_message_tenant_id"),
        ForeignKeyConstraint(
            ["conversation_id", "tenant_id"],
            ["chat_conversation.id", "chat_conversation.tenant_id"],
            name="fk_chat_message_conversation_tenant",
        ),
        CheckConstraint("sequence >= 1", name="ck_chat_message_sequence"),
        CheckConstraint("length(body) BETWEEN 1 AND 4000", name="ck_chat_message_body_length"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    conversation_id: uuid.UUID = Field(index=True)
    tenant_id: str = Field(index=True, max_length=255)
    sequence: int = Field(ge=1)
    sender_subject: str = Field(index=True, max_length=255)
    sender_name: str = Field(default="", max_length=255)
    client_message_id: uuid.UUID
    body: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column(index=True))
