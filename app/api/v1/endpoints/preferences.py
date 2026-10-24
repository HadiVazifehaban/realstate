"""Per-user preferences: the caller's own UI settings, keyed by token subject.

``GET /users/me/preferences`` returns the caller's map (``{"active_city": "تهران"}``).
``PUT /users/me/preferences`` upserts it.  No manager gate: a caller may only
read or write their *own* row set (``principal.subject``), never another
user's -- which is why there is no ``{user_id}`` in the path.

The Shekarchi City Gate reads this on login: the server copy wins over the
browser's localStorage, so a city picked on one device follows the user to
the next login anywhere.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlmodel import select

from fastapi import APIRouter

from app.api.deps import PrincipalDep, SessionDep
from app.models.user_preference import UserPreference

router = APIRouter()

#: Preference keys the API accepts. Unknown keys are ignored, never stored --
#: the table is not a free-form client attic.
ALLOWED_KEYS = frozenset({"active_city"})


class PreferencesOut(BaseModel):
    preferences: dict[str, str] = Field(default_factory=dict)


class PreferencesIn(BaseModel):
    preferences: dict[str, str] = Field(default_factory=dict)


@router.get("/me/preferences", response_model=PreferencesOut)
async def get_my_preferences(
    session: SessionDep,
    principal: PrincipalDep,
) -> PreferencesOut:
    """The caller's own preference map (empty when never saved)."""
    rows = (
        await session.exec(
            select(UserPreference).where(UserPreference.subject == principal.subject)
        )
    ).all()
    return PreferencesOut(preferences={row.key: row.value for row in rows})


@router.put("/me/preferences", response_model=PreferencesOut)
async def put_my_preferences(
    body: PreferencesIn,
    session: SessionDep,
    principal: PrincipalDep,
) -> PreferencesOut:
    """Upsert the caller's preference map (allowed keys only)."""
    wanted = {
        key: value.strip() if isinstance(value, str) else ""
        for key, value in (body.preferences or {}).items()
        if key in ALLOWED_KEYS
    }
    existing = (
        await session.exec(
            select(UserPreference).where(UserPreference.subject == principal.subject)
        )
    ).all()
    by_key = {row.key: row for row in existing}
    for key, value in wanted.items():
        row = by_key.get(key)
        if row is None:
            session.add(
                UserPreference(subject=principal.subject, key=key, value=value)
            )
        elif row.value != value:
            row.value = value
            session.add(row)
    await session.commit()
    rows = (
        await session.exec(
            select(UserPreference).where(UserPreference.subject == principal.subject)
        )
    ).all()
    return PreferencesOut(preferences={row.key: row.value for row in rows})


__all__ = ["router"]
