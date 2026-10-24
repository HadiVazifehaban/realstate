"""Re-derive listing identity from already-stored crawler payloads.

Usage::

    python -m app.cli.backfill_listings --dry-run
    python -m app.cli.backfill_listings
    python -m app.cli.backfill_listings --limit 50

Why this exists
---------------
The first ingestion runs predated the ``seo.post_seo_schema`` lookup in
:mod:`app.services.scraper.parser`. That parser walked the payload for the first
``title`` it could find, and a Divar post payload opens with ``sections`` whose
first widget is the *agency* profile -- so every crawled row was stored with the
agency's name as its title and, because ``build_property_fields`` only filled the
PostGIS ``location`` column, without the scalar latitude/longitude the API
projects. No gallery row was ever written either.

All three fields are already present in ``property.raw_data``: the crawler keeps
the whole post payload, so this rewrites the columns by re-parsing it. It needs
no network access and no re-crawl, and it is idempotent -- a second run finds
nothing left to change.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from sqlmodel import select

from app.db.session import AsyncSessionLocal
from app.models import Property, PropertyMedia
from app.models.enums import PropertySource
from app.services.ingestion.pipeline import sync_property_media
from app.services.ingestion.sanitizer import to_ewkt_point
from app.services.scraper.parser import parse_post_detail

#: ``parse_post_detail`` speaks Divar's schema only, so a Sheypoor payload would
#: be rewritten into nonsense rather than improved.
_DIVAR_SOURCES = (
    PropertySource.DIVAR,
    PropertySource.DIVAR_SCRAPER,
    PropertySource.DIVAR_KENAR,
)


async def _backfill(session: Any, *, limit: int | None, dry_run: bool) -> dict[str, int]:
    """Rewrite identity fields for every crawled listing, newest first."""
    stmt = select(Property).where(
        Property.raw_data.is_not(None),
        Property.source.in_(_DIVAR_SOURCES),
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    rows = (await session.exec(stmt.order_by(Property.created_at.desc()))).all()

    stats = {"scanned": 0, "title": 0, "place": 0, "geo": 0, "media": 0, "skipped": 0}
    for prop in rows:
        stats["scanned"] += 1
        payload = prop.raw_data
        if not isinstance(payload, dict) or not payload:
            stats["skipped"] += 1
            continue

        detail = parse_post_detail(payload, prop.external_id or prop.code)
        changed = False

        # A blank title is as useless as a wrong one, so an empty SEO block
        # never overwrites a real headline with "".
        if detail.title and detail.title != prop.title:
            prop.title = detail.title
            stats["title"] += 1
            changed = True

        if (detail.city, detail.neighborhood) != (prop.city, prop.neighborhood):
            if detail.city:
                prop.city = detail.city
            if detail.neighborhood:
                prop.neighborhood = detail.neighborhood
            stats["place"] += 1
            changed = True

        if (
            detail.latitude is not None
            and detail.longitude is not None
            and (prop.latitude != detail.latitude or prop.longitude != detail.longitude)
        ):
            prop.latitude = detail.latitude
            prop.longitude = detail.longitude
            point = to_ewkt_point(detail.latitude, detail.longitude)
            if point is not None:
                prop.location = point
            stats["geo"] += 1
            changed = True

        if not changed and not detail.images:
            continue

        if not dry_run:
            added = await sync_property_media(session, prop.id, detail.images)
            stats["media"] += added
            if added:
                await session.commit()
                continue
            if changed:
                await session.commit()
        else:
            known = await _existing_media_count(session, prop.id)
            stats["media"] += max(0, len(detail.images) - known)

    if not dry_run:
        await session.commit()
    return stats


async def _existing_media_count(session: Any, property_id: Any) -> int:
    rows = (
        await session.exec(
            select(PropertyMedia).where(PropertyMedia.property_id == property_id)
        )
    ).all()
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.backfill_listings",
        description="Re-derive title, place names, coordinates and gallery "
        "from property.raw_data.",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Only touch N rows (newest first)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing.",
    )
    args = parser.parse_args(argv)

    async def _run() -> dict[str, int]:
        async with AsyncSessionLocal() as session:
            return await _backfill(session, limit=args.limit, dry_run=args.dry_run)

    stats = asyncio.run(_run())
    prefix = "would fix" if args.dry_run else "fixed"
    print(
        f"scanned={stats['scanned']} skipped={stats['skipped']} "
        f"{prefix} title={stats['title']} place={stats['place']} "
        f"geo={stats['geo']} media={stats['media']}",
        file=sys.stderr if args.dry_run else sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())