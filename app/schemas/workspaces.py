"""Workspace API contracts."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class WorkspaceSummary(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    name_fa: str
    status: str
    role: str