"""Geospatial helpers: OSM reverse geocoding and distance utilities.

The office node runs offline-first, so a geocoder outage must degrade
gracefully (an empty district) rather than block a submission. The actual
remote call lives in :mod:`app.services.osm_service`; this module owns the
distance maths and the privacy blur, and is the seam the rest of the app calls.
"""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger("app.geo")

# Nomination cache lifetime: admin boundaries change rarely.
GEOCODE_CACHE_DAYS = 30

#: Radius of the area a listing is published within when its exact pin is
#: withheld. Single source of truth: the summary endpoint hands this number to
#: the browser so the map can draw the same circle the backend would mask to,
#: instead of the two drifting apart (they did -- 300m here, 900m in the map
#: component, 200m in the phase plan).
PRIVACY_BLUR_RADIUS_M = 200.0


def point_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    radius = 6_371_000.0
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def blur_point(
    latitude: float, longitude: float, radius_m: float = PRIVACY_BLUR_RADIUS_M
) -> tuple[float, float]:
    """Fuzz a coordinate for MLS sharing.

    Deterministic (no RNG) so the same listing always masks to the same point:
    an observer cannot correlate two shares of the same unit.
    """
    import hashlib

    digest = hashlib.sha256(f"{latitude:.5f},{longitude:.5f}".encode()).digest()
    angle = (digest[0] / 255.0) * 2 * math.pi
    offset = radius_m * (0.5 + (digest[1] / 255.0) * 0.5)  # 0.5r .. r
    lat_scale = 111_320.0
    lon_scale = 111_320.0 * max(0.01, math.cos(math.radians(latitude)))
    return (
        latitude + (offset * math.cos(angle)) / lat_scale,
        longitude + (offset * math.sin(angle)) / lon_scale,
    )


async def reverse_geocode(
    session: AsyncSession,
    latitude: float,
    longitude: float,
    settings: Settings,
) -> dict[str, Any]:
    """Look up Persian administrative fields for a coordinate via OSM.

    Cache-first, so a busy office node still issues one OSM call per ~50 m
    grid cell. A node with ``osm_enabled=false`` degrades to an empty district
    instead of failing the submission.
    """
    from app.services import osm_service

    if not settings.osm_enabled:
        return {}
    entry = await osm_service.cached_nominatim_reverse_geocode(
        session, latitude, longitude, settings
    )
    return {
        "province": entry.get("province", ""),
        "city": entry.get("city", ""),
        "district": entry.get("district", ""),
        "neighborhood": entry.get("neighborhood", ""),
        "display_name": entry.get("display_name", ""),
        "municipality_zone": entry.get("municipality_zone", ""),
        "formatted_address": entry.get("formatted_address", ""),
        "in_traffic_zone": entry.get("in_traffic_zone"),
        "in_odd_even_zone": entry.get("in_odd_even_zone"),
    }