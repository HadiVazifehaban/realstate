"""Merge the workspace/referral and internal-chat migration heads."""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "4f8b2d1c6a90"
down_revision: tuple[str, str] = ("c2f71a4d9b30", "8d4a1c7e9b20")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass