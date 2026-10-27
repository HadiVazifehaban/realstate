"""Request and response contracts for tenant-scoped internal chat."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatConversationCreate(BaseModel):
    title: str = Field(default="", max_length=160)
    member_subjects: list[str] = Field(min_length=1, max_length=50)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return value.strip()

    @field_validator("member_subjects")
    @classmethod
    def validate_member_subjects(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 255 for value in normalized):
            raise ValueError("member subjects must contain 1 to 255 characters")
        if len(set(normalized)) != len(normalized):
            raise ValueError("member subjects must be unique")
        return normalized


class ChatMessageCreate(BaseModel):
    client_message_id: uuid.UUID
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("message body cannot be blank")
        return normalized


class ChatMemberRead(BaseModel):
    subject: str
    display_name: str


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequence: int
    sender_subject: str
    sender_name: str
    client_message_id: uuid.UUID
    body: str
    created_at: datetime


class ChatConversationRead(BaseModel):
    id: uuid.UUID
    title: str
    created_by_subject: str
    created_at: datetime
    members: list[ChatMemberRead]
    last_message: ChatMessageRead | None = None
