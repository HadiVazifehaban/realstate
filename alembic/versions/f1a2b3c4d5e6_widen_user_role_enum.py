"""Phase 5 fix: widen ``user_role`` to the seven-tier RBAC ladder.

Revision ID: f1a2b3c4d5e6
Revises: e2f4a6b8c9d1

``c63691ed7bdc`` created ``user_role`` with the Phase 1 four-role vocabulary
(``ADMIN`` / ``MANAGER`` / ``AGENT`` / ``VIEWER``).  ``e2f4a6b8c9d1`` declared the
new seven-tier ladder but created it with ``checkfirst=True``, which silently
skipped the type because it already existed -- so every value outside the
original four (``OFFICE_MANAGER``, ``SUPERVISOR``, ``GUEST``, ``USER``,
``OWNER``) failed with ``invalid input value for enum user_role`` on insert.

PostgreSQL cannot drop an enum value in place, so the type is recreated and
``agency_user.role`` cast across.  The two retired labels are folded into their
closest surviving role so no existing row is lost.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e2f4a6b8c9d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ROLE_LABELS = (
    "GUEST", "USER", "OWNER", "AGENT",
    "OFFICE_MANAGER", "SUPERVISOR", "ADMIN",
)
#: Phase 1 labels retired by the ladder, mapped onto their replacement.
LEGACY_TO_NEW = {"MANAGER": "OFFICE_MANAGER", "VIEWER": "USER"}
#: Reverse mapping used by :func:`downgrade`.
NEW_TO_LEGACY = {
    "OFFICE_MANAGER": "MANAGER",
    "SUPERVISOR": "MANAGER",
    "GUEST": "VIEWER",
    "USER": "VIEWER",
    "OWNER": "AGENT",
}


def _labels(type_name: str) -> list[str]:
    """Read the live labels of a native enum (empty when the type is absent)."""
    if context.is_offline_mode():
        # Offline SQL is generated from the known preceding revision graph;
        # querying pg_catalog is impossible without a live bind.
        return list(ROLE_LABELS) if type_name == "user_role" else []
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT e.enumlabel FROM pg_enum e "
            "JOIN pg_type t ON t.oid = e.enumtypid WHERE t.typname = :name"
        ),
        {"name": type_name},
    ).scalars().all()
    return [str(row) for row in rows]


def _recast(column: str, mapping: dict[str, str], target: str) -> None:
    """Cast ``agency_user.<column>`` onto ``target``, folding legacy labels."""
    when = " ".join(
        f"WHEN '{old}' THEN '{new}'" for old, new in mapping.items()
    )
    op.execute(
        f"ALTER TABLE agency_user ALTER COLUMN {column} TYPE {target} USING ("
        f"CASE {column}::text {when} ELSE {column}::text END"
        f")::{target}"
    )


def upgrade() -> None:
    labels = _labels("user_role")
    if set(ROLE_LABELS).issubset(labels):
        return  # already widened -- keep the migration replayable

    enum_labels = ", ".join(f"'{label}'" for label in ROLE_LABELS)
    op.execute('ALTER TYPE user_role RENAME TO "user_role_old"')
    op.execute(f"CREATE TYPE user_role AS ENUM ({enum_labels})")
    _recast("role", LEGACY_TO_NEW, "user_role")
    op.execute('DROP TYPE "user_role_old"')


def downgrade() -> None:
    labels = set(_labels("user_role"))
    if labels == {"ADMIN", "MANAGER", "AGENT", "VIEWER"}:
        return

    op.execute('ALTER TYPE user_role RENAME TO "user_role_old"')
    op.execute(
        "CREATE TYPE user_role AS ENUM ('ADMIN', 'MANAGER', 'AGENT', 'VIEWER')"
    )
    _recast("role", NEW_TO_LEGACY, "user_role")
    op.execute('DROP TYPE "user_role_old"')
