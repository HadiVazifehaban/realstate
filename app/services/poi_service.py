"""Nearby points of interest, from OSM (Nominatim and Overpass).

Why this is cached
------------------
Every POI lookup is an upstream HTTP call, and a detail page renders one on open
-- so a broker clicking through ten listings would spend ten quota units on the
same street. The answer is therefore stored against a ~111 m grid cell
(``poi_cache``) for seven days: within a week the block's amenities do not
meaningfully change, and every listing on that street shares one row.

How a lookup is answered
------------------------
A listing asks for everything within ``radius_m``, but the cache is per cell and
111 m < any useful radius. So two steps:

1. ``ST_DWithin`` over ``poi_cache.point`` selects every cached cell whose centre
   falls inside the requested circle. The GiST index makes this a cheap index
   scan rather than a table scan. Cached rows are merged, de-duplicated, and
   re-sorted by distance.
2. If the listing's own cell has no fresh row, OSM (Overpass) is queried once for
   that cell and written back before the merge.

A portal failure is never fatal: if OSM/Overpass is unreachable, the endpoint
returns an empty bucket for the missing cell rather than failing the page. A
detail page that renders with an empty "amenities nearby" block is much better
than one that does not render.

This service runs on the node's own tiles data with OpenStreetMap (Overpass)
behind it, so it needs no map-provider key.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.poi_cache import (
    POI_CELL_DEGREES,
    PoiCache,
    cell_for,
    is_fresh,
)
from app.services import osm_service
from app.services.ingestion.sanitizer import to_ewkt_point

logger = logging.getLogger("app.poi")

#: Buckets, in the order the detail page renders them. Values are the Persian
#: heading shown to the advisor.
BUCKETS: dict[str, str] = {
    "transport": "حمل و نقل عمومی",
    "shopping": "مراکز خرید",
    "education": "آموزشی",
    "healthcare": "درمانی و سلامت",
    "leisure": "تفریحی و ورزشی",
}

#: OSM/Overpass layer that answers each bucket (مینی پلاسمايي از نامزدن).
#: Persian titles are taken from OSM's standard tags, so the heading matches the
#: source the advisor reads from rather than being re-derived.
NEARBY_LAYERS: dict[str, list[str]] = {
    "transport": ["transit_station", "bus_station", "train_station", "metro_entrance"],
    "shopping": ["shopping_mall", "vegetable_market"],
    "education": ["formal_school", "university", "studying_center"],
    "healthcare": ["hospital", "clinic", "health_complex"],
    "leisure": ["park", "garden", "gym", "stadium"],
}

#: Cap per bucket so one dense commercial street cannot push the page's payload
#: to megabytes. Nearest-first, so the cut keeps the most relevant names.
MAX_PER_BUCKET = 5

#: URL for this node's self-hosted tiles PostGIS database, which holds the
#: ``planet_osm_point`` table used for POI enrichment. It replaces the upstream map
#: HTTP call: the data lives one network hop away, is indexed for a fast
#: radial query, and does not count against any vendor quota. Override the default
#: connection by setting the ``TILES_DB_URL`` environment variable.
_TILES_DB_URL = os.getenv(
    "TILES_DB_URL",
    "postgresql+psycopg://renderer:renderer@avg_tiles:5432/gis",
)

#: Lazy-loaded async engine for the tiles database. Connections are pooled per
#: process so the per-lookup cost is just an engine.acquire().
_tiles_engine = None


def _get_tiles_engine():
    global _tiles_engine
    if _tiles_engine is None:
        from sqlalchemy.ext.asyncio import create_async_engine

        _tiles_engine = create_async_engine(
            _TILES_DB_URL,
            pool_pre_ping=True,
            future=True,
        )
    return _tiles_engine


@asynccontextmanager
async def _tiles_connect():
    """Yield a live connection to the tiles PostGIS, closing it when done."""
    engine = _get_tiles_engine()
    async with engine.connect() as conn:
        yield conn


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Metres between two WGS84 points.

    Computed rather than trusted from the payload: Overpass does not return a
    distance for ``around``, and the merged result spans several cells, so the
    ordering has to be recomputed from the listing's own pin.
    """
    from app.services.geo import point_distance_m

    return point_distance_m(lat1, lon1, lat2, lon2)


async def _cached_cells_within(
    session: AsyncSession, lat: float, lng: float, radius_m: float
) -> list[dict[str, Any]]:
    """Every cached cell whose centre is inside the circle, via ST_DWithin."""
    result = await session.execute(
        text(
            """
            SELECT cell_lat, cell_lng, payload, fetched_at
            FROM poi_cache
            WHERE ST_DWithin(
                point,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                :radius
            )
            """
        ),
        {"lat": lat, "lng": lng, "radius": radius_m},
    )
    return [dict(row._mapping) for row in result]


def _bucket_of(tags: dict[str, Any]) -> str | None:
    """Which bucket an Overpass node belongs to, or ``None`` if unnamed.

    A park is written ``leisure=park`` in OSM's schema, but the tiles import
    keeps whatever the mapper typed, so a handful carry ``amenity=park``. Both
    are read rather than assumed: a park missing from the "amenities nearby"
    block on a listing that is 200 m from one is the kind of gap a buyer reads
    as a missing feature of the property.
    """
    amenity = tags.get("amenity")
    if amenity in {
        "bus_station", "taxi", "school", "kindergarten", "college",
        "university", "hospital", "clinic", "pharmacy", "doctors",
    } or tags.get("railway") == "station":
        if amenity in {"bus_station", "taxi"} or tags.get("railway") == "station":
            return "transport"
        if amenity in {"school", "kindergarten", "college", "university"}:
            return "education"
        return "healthcare"
    if tags.get("shop"):
        return "shopping"
    if tags.get("leisure") in {
        "park", "playground", "fitness_centre", "sports_centre"
    } or amenity == "park":
        return "leisure"
    return None


async def nearby_pois_from_tiles(lat: float, lng: float, radius_m: int) -> dict[str, list[dict[str, Any]]]:
    """Primary POI source: named amenities in the self-hosted tiles PostGIS.

    ``planet_osm_point`` is indexed on ``way`` (GIST), so the ``ST_DWithin``
    predicate below is an index scan that answers a 500 m radius in
    milliseconds. Only named features are returned: an unnamed node carries no
    signal for a buyer-facing list and only consumes list space.

    The result is a plain dict of buckets so the caller can cache it exactly like
    an Overpass response and treat every source uniformly below.
    """
    query = text(
        """
        SELECT
            name,
            amenity,
            shop,
            leisure,
            ST_Y(ST_Transform(way, 4326)) AS lat,
            ST_X(ST_Transform(way, 4326)) AS lng
        FROM planet_osm_point
        WHERE name IS NOT NULL
          AND ST_DWithin(
                way,
                ST_Transform(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), 3857),
                :radius
              )
        ORDER BY ST_Distance(
            way,
            ST_Transform(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), 3857)
        )
        """
    )
    buckets: dict[str, list[dict[str, Any]]] = {key: [] for key in BUCKETS}
    async with _tiles_connect() as conn:
        result = await conn.execute(query, {"lat": lat, "lng": lng, "radius": radius_m})
        for row in result.mappings():
            name = row["name"]
            if not name:
                continue
            bucket = _bucket_of(
                {
                    "name": name,
                    "amenity": row["amenity"],
                    "shop": row["shop"],
                    "leisure": row["leisure"],
                }
            )
            if bucket is None:
                continue
            buckets[bucket].append(
                {"name": str(name), "lat": float(row["lat"]), "lng": float(row["lng"])}
            )
    return buckets


def _parse_overpass(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Group Overpass elements into named, positioned POIs per bucket."""
    buckets: dict[str, list[dict[str, Any]]] = {key: [] for key in BUCKETS}
    for element in payload.get("elements") or []:
        tags = element.get("tags") or {}
        name = tags.get("name")
        lat, lng = element.get("lat"), element.get("lon")
        # An unnamed node ("پارک" with no name) is noise in a buyer-facing list.
        if not name or lat is None or lng is None:
            continue
        bucket = _bucket_of(tags)
        if bucket is None:
            continue
        buckets[bucket].append(
            {"name": str(name), "lat": float(lat), "lng": float(lng)}
        )
    return buckets


async def _fetch_from_osm(
    lat: float, lng: float, radius_m: int, settings: Settings
) -> dict[str, list[dict[str, Any]]]:
    """Query Overpass, one call per bucket layer.

    Reached only when the tiles database is unreachable, which is why the
    Overpass calls -- a rated public service with no SLA -- are acceptable
    here: they are the fallback, not the path a healthy node takes. Every
    layer is asked at once and a failure on one only empties that bucket.
    """
    s = settings
    jobs = [
        (bucket, layer)
        for bucket, layers in NEARBY_LAYERS.items()
        for layer in layers
    ]
    results = await asyncio.gather(
        *(osm_service.search_nearby(lat, lng, layer, radius_m) for _bucket, layer in jobs),
        return_exceptions=True
    )

    buckets: dict[str, list[dict[str, Any]]] = {key: [] for key in BUCKETS}

    for (bucket, _layer), places in zip(jobs, results):
        # A layer answering with nothing is normal; only a raised exception says
        # the call itself failed, and even that costs one bucket, not the page.
        if isinstance(places, BaseException):
            logger.warning("Overpass nearby %s failed for %s,%s: %s", _layer, lat, lng, places)
            continue
        _merge(buckets, bucket, places)

    return buckets


def _merge(
    buckets: dict[str, list[dict[str, Any]]], bucket: str, places: list[dict[str, Any]]
) -> None:
    """Add places to a bucket, dropping same-position duplicates.

    Two layers in one bucket can name the same place (``school`` and
    ``university`` overlap heavily), and without this the advisor sees a
    duplicate row in a five-item list where duplicates are a third of the
    content.
    """
    known = {f"{p['name']}@{p['lat']:.6f},{p['lng']:.6f}" for p in buckets[bucket]}
    for place in places:
        if not place.get("name"):
            continue
        identity = f"{place['name']}@{place['lat']:.6f},{place['lng']:.6f}"
        if identity in known:
            continue
        known.add(identity)
        buckets[bucket].append(place)


async def fetch_nearby(
    lat: float, lng: float, radius_m: int, settings: Settings | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Named amenities around a point.

    Primary source is this node's own PostGIS tiles database (``planet_osm_point``),
    which answers a sub-500 m radius in milliseconds and needs no upstream call.
    If that database is unreachable this falls back to Overpass, one request
    per bucket layer. Every failure returns empty buckets -- a detail page that
    renders with an empty "amenities nearby" block is much better than one that
    does not render at all.
    """
    s = settings or get_settings()

    try:
        return await nearby_pois_from_tiles(lat, lng, radius_m)
    except Exception as exc:
        logger.warning("tiles POI lookup failed for %s,%s: %s", lat, lng, exc)

    try:
        return await _fetch_from_osm(lat, lng, radius_m, s)
    except Exception as exc:  # noqa: BLE001 - enrichment must never fail a page
        logger.warning("Overpass lookup failed for %s,%s: %s", lat, lng, exc)
        return {key: [] for key in BUCKETS}


async def _ensure_centre_cell(
    session: AsyncSession, lat: float, lng: float, radius_m: int, settings: Settings
) -> None:
    """Fetch and cache the listing's own cell when it has no fresh row.

    ``nearby_poi`` merges every cached cell inside the circle; that merge only
    covers what is already stored. This step guarantees the centre cell itself
    is fresh first, fetching it from the tiles DB (falling back to Overpass)
    via ``fetch_nearby`` and writing the answer back, so the merge below has
    something to work with. A fetch failure only logs -- the endpoint still
    returns whatever neighbours are already cached rather than failing.
    """
    from sqlmodel import select

    cell_lat, cell_lng = cell_for(lat, lng)
    existing = (
        await session.exec(
            select(PoiCache).where(
                PoiCache.cell_lat == cell_lat, PoiCache.cell_lng == cell_lng
            )
        )
    ).first()
    if existing is not None and is_fresh(existing.fetched_at):
        return
    try:
        payload = await fetch_nearby(lat, lng, radius_m, settings)
    except Exception as exc:  # noqa: BLE001 - enrichment must never fail a page
        logger.warning("centre-cell POI fetch failed for %s,%s: %s", lat, lng, exc)
        return
    row = existing if existing is not None else PoiCache(cell_lat=cell_lat, cell_lng=cell_lng)
    row.payload = payload
    row.point = to_ewkt_point(cell_lat, cell_lng)
    from app.models.base import utcnow

    row.fetched_at = utcnow()
    session.add(row)
    try:
        await session.commit()
    except Exception as exc:  # noqa: BLE001 - a lost race is still a miss
        logger.warning("centre-cell POI cache write failed: %s", exc)
        await session.rollback()


async def nearby_poi(
    session: AsyncSession,
    lat: float,
    lng: float,
    *,
    radius_m: int = 500,
    settings: Settings | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Buckets of named POIs within ``radius_m``, nearest first.

    Always returns every bucket key, even when empty, so the page can render a
    stable set of cards instead of a list that reflows as data arrives.
    """
    s = settings or get_settings()
    await _ensure_centre_cell(session, lat, lng, radius_m, s)

    rows = await _cached_cells_within(session, lat, lng, radius_m)
    merged: dict[str, list[dict[str, Any]]] = {key: [] for key in BUCKETS}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if not is_fresh(row["fetched_at"]):
            continue
        for key, items in (row["payload"] or {}).items():
            bucket = merged.setdefault(key, [])
            for item in items:
                marker = (item.get("name", ""), f"{item.get('lat')},{item.get('lng')}")
                if marker in seen:
                    continue
                seen.add(marker)
                bucket.append(item)

    # Several cells overlap in the distance sense, so re-sort against the real
    # pin and cut to the per-bucket cap only after merging.
    for key, items in merged.items():
        items.sort(key=lambda i: _haversine_m(lat, lng, i["lat"], i["lng"]))
        for item in items:
            item["distance_m"] = round(_haversine_m(lat, lng, item["lat"], item["lng"]))
        merged[key] = items[:MAX_PER_BUCKET]
    return merged


__all__ = [
    "BUCKETS",
    "MAX_PER_BUCKET",
    "POI_CELL_DEGREES",
    "fetch_overpass",
    "nearby_poi",
]