"""``PropertyOwnerPII`` -- isolated, encrypted owner information vault.

This table never leaves the on-premise node in plaintext.  Columns hold Fernet
tokens produced by :class:`app.core.crypto.PiiCipher`; ``*_blind_index`` columns
hold deterministic HMAC digests used for exact-match search without decryption.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import SQLModel, Field, Relationship

from app.models.base import timestamp_column, utcnow, uuid_column


class PropertyOwnerPII(SQLModel, table=True):
    """Sensitive owner data for one property (encrypted at rest)."""

    __tablename__ = "property_owner_pii"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    property_id: uuid.UUID = Field(foreign_key="property.id", index=True, unique=True)

    # Fernet-encrypted fields (ciphertext, base64)
    owner_name_enc: str | None = Field(default=None, max_length=1024)
    owner_phone_enc: str | None = Field(default=None, max_length=1024)
    owner_phone_alt_enc: str | None = Field(default=None, max_length=1024)
    exact_address_enc: str | None = Field(default=None, max_length=4096)
    pelak_unit_enc: str | None = Field(default=None, max_length=1024)
    national_id_enc: str | None = Field(default=None, max_length=1024)

    # Deterministic blind indexes (searchable without decryption)
    owner_phone_bindex: str | None = Field(default=None, max_length=128, index=True)
    owner_name_bindex: str | None = Field(default=None, max_length=128, index=True)

    # Which advisor registered the owner (access-control anchor)
    created_by_id: uuid.UUID | None = Field(default=None, foreign_key="agency_user.id")

    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
