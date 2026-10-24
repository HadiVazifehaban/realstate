"""One-off backfill: demote non-city values out of ``Property.city``.

Usage (inside the backend container)::

    docker compose exec backend python -m app.cli.backfill_city [--apply]

Without ``--apply`` it only reports what *would* change.  With ``--apply`` it
writes: non-city ``city`` values move to ``neighborhood`` (when empty),
``city`` becomes ``""``.

Safe to re-run: rows already holding a known city (or empty) are skipped.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import update
from sqlmodel import select

from app.db.session import AsyncSessionLocal
from app.models import Property
from app.services.city_normalizer import normalize_city_neighborhood


async def plan(session) -> list[tuple[str, str, str, str]]:
    """Rows whose city slot holds a non-city. Returns (id, old_city, new_city, new_area)."""
    rows = (await session.exec(select(Property).where(Property.city != ""))).all()
    out = []
    for row in rows:
        new_city, new_area = normalize_city_neighborhood(row.city, row.neighborhood)
        if new_city != row.city or new_area != (row.neighborhood or ""):
            out.append((str(row.id), row.city, new_city, new_area))
    return out


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes to the DB")
    args = parser.parse_args()

    async with AsyncSessionLocal() as session:
        changes = await plan(session)
        print(f"rows to fix: {len(changes)}")
        for row_id, old_city, new_city, new_area in changes[:50]:
            print(f"  {row_id[:8]}  {old_city!r}  ->  city={new_city!r} area={new_area!r}")
        if len(changes) > 50:
            print(f"  ... and {len(changes) - 50} more")
        if not args.apply:
            print("dry-run only; re-run with --apply to write.")
            return
        for row_id, _old_city, new_city, new_area in changes:
            await session.exec(
                update(Property)
                .where(Property.id == row_id)
                .values(city=new_city, neighborhood=new_area)
            )
        await session.commit()
        print(f"updated {len(changes)} rows.")


if __name__ == "__main__":
    asyncio.run(main())
