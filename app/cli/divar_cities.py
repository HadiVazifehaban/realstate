"""Inspect and refresh the Divar city/district registry.

Usage::

    python -m app.cli.divar_cities list
    python -m app.cli.divar_cities show tehran
    python -m app.cli.divar_cities verify tehran

``verify`` performs a real search against Divar and confirms that the
configured ``city_id`` actually returns listings. It needs an egress IP that
Divar accepts (this project's dev/CI network gets 403 AccessDenied).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.services.scraper import cities


def _cmd_list(_args: argparse.Namespace) -> int:
    print(cities.format_registry_markdown())
    unverified = cities.unverified_cities()
    print(f"\n{len(cities.CITIES)} cities, {len(unverified)} unverified")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    try:
        entry = cities.get_city(args.city)
    except cities.UnknownCityError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({
        "slug": entry.slug,
        "city_id": entry.city_id,
        "persian": entry.persian,
        "districts": entry.districts,
        "is_verified": entry.is_verified,
    }, ensure_ascii=False, indent=2))
    return 0


async def _verify_async(city: str) -> int:
    from app.services.scraper.divar_client import DivarClient

    async with DivarClient() as client:
        payload = await client.search(city, "apartment-sell", 1)
    widgets = payload.get("list_widgets") if isinstance(payload, dict) else None
    count = len(widgets) if isinstance(widgets, list) else 0
    print(f"city={city} city_id={cities.resolve_city_id(city)} listings_on_page={count}")
    if count == 0:
        print(
            "WARNING: zero listings — the city id is likely stale. "
            "Update app/services/scraper/cities.py.",
            file=sys.stderr,
        )
        return 1
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    try:
        cities.get_city(args.city)
    except cities.UnknownCityError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        return asyncio.run(_verify_async(args.city))
    except Exception as exc:  # network/registry errors stay readable
        print(f"verify failed: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="avg-divar-cities",
        description="Inspect/refresh the Divar city registry.",
    )
    # Positional sub-commands: ``--list`` style names are rejected by argparse
    # when declared as required sub-parsers, so use plain verbs.
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="print the registry as a markdown table").set_defaults(
        func=_cmd_list
    )

    show = sub.add_parser("show", help="print one city as JSON")
    show.add_argument("city")
    show.set_defaults(func=_cmd_show)

    verify = sub.add_parser("verify", help="live-check a city id by searching Divar")
    verify.add_argument("city")
    verify.set_defaults(func=_cmd_verify)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())