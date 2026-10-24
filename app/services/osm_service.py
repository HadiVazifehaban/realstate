"""OpenStreetMap GIS gateway using Nominatim and Overpass APIs.

This module provides a pure OpenStreetMap-based GIS service that replaces
the map-provider stack it replaced. It uses:
- Nominatim for geocoding and reverse geocoding
- Overpass API for nearby points of interest and administrative areas
- Self-hosted OSM tile server for map tiles (already configured separately)
"""

from __future__ import annotations

from time import monotonic
from typing import Any, Dict, List

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("app.osm")

#: Nominatim matches on free text, so the country is part of the query. It is
#: Persian because the query is built from a Persian address, and Nominatim's
#: name index ranks a same-script match higher than a transliteration.
COUNTRY = "ایران"

# Cache TTLs (in seconds)
AREAS_CACHE_TTL_SECONDS = 86_400  # 1 day for administrative areas
NOMINATIM_CACHE_TTL_SECONDS = 3600  # 1 hour for geocoding


class OsmAPIError(Exception):
    """Osm API error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


def _build_nominatim_url(path: str) -> str:
    """Build Nominatim API URL."""
    base_url = get_settings().nominatim_base_url.rstrip("/")
    return f"{base_url}{path}"


def _build_overpass_url() -> str:
    """Build Overpass API URL."""
    return get_settings().overpass_endpoint


def _timeout() -> float:
    return get_settings().osm_timeout_seconds


async def _make_nominatim_request(
    path: str,
    params: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Make a request to the Nominatim API."""
    url = _build_nominatim_url(path)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                url,
                params=params,
                timeout=_timeout(),
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("Nominatim HTTP error: %s - %s", e.response.status_code, e.response.text)
            raise OsmAPIError(
                f"Nominatim error: {e.response.status_code} {e.response.text}",
                status_code=e.response.status_code,
            ) from e
        except Exception as e:
            logger.error("Nominatim request failed: %s", e)
            raise OsmAPIError(f"Nominatim request failed: {e}") from e


async def _make_overpass_request(query: str) -> Dict[str, Any]:
    """Make a request to the Overpass API."""
    url = _build_overpass_url()
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                data={"data": query},
                timeout=_timeout(),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("Overpass HTTP error: %s - %s", e.response.status_code, e.response.text)
            raise OsmAPIError(
                f"Overpass error: {e.response.status_code} {e.response.text}",
                status_code=e.response.status_code,
            ) from e
        except Exception as e:
            logger.error("Overpass request failed: %s", e)
            raise OsmAPIError(f"Overpass request failed: {e}") from e


async def reverse_geocode(
    lat: float,
    lng: float,
) -> Dict[str, Any]:
    """Reverse geocode a coordinate using Nominatim.
    
    Returns administrative fields in the CRM's own flat format, which is
    unchanged from before, so every caller reads the same keys.
    """
    if not get_settings().osm_enabled:
        return {}
    
    # Nominatim reverse geocoding endpoint
    params = {
        "lat": lat,
        "lon": lng,
        "format": "json",
        "addressdetails": 1,
        "extratags": 1,
        "namedetails": 1,
    }
    
    try:
        data = await _make_nominatim_request("/reverse", params)
    except OsmAPIError:
        return {}
    
    if not isinstance(data, dict):
        return {}
    
    # Extract address details
    address = data.get("address", {})
    extratags = data.get("extratags", {})
    namedetails = data.get("namedetails", {})
    
    # Build the flat CRM field set
    result: Dict[str, Any] = {
        "formatted_address": data.get("display_name", ""),
        "neighbourhood": "",
        "neighborhood": "",
        "municipality_zone": "",
        "city": "",
        "state": "",
        "province": "",
        "district": "",
        "region": "",
        "place": "",
        "village": "",
        "route_name": "",
        "route_type": "",
        "in_traffic_zone": None,
        "in_odd_even_zone": None,
    }
    
    # Map Nominatim fields to our expected format
    # Note: Nominatim uses different keys, we map them appropriately
    result["formatted_address"] = data.get("display_name", "")
    
    # Neighborhood/suburb
    result["neighbourhood"] = address.get("suburb", "") or address.get("neighbourhood", "")
    result["neighborhood"] = result["neighbourhood"]
    
    # City/town/village
    result["city"] = (
        address.get("city") or 
        address.get("town") or 
        address.get("village") or 
        address.get("hamlet") or
        ""
    )
    
    # Province/state
    result["state"] = address.get("state", "")
    result["province"] = result["state"]  # In Iran context, state = province
    
    # County/district
    result["district"] = (
        address.get("county") or 
        address.get("district") or 
        address.get("municipality") or
        ""
    )
    
    # Additional fields
    result["municipality_zone"] = address.get("municipality", "")
    result["region"] = address.get("state_district", "")
    result["place"] = address.get("locality", "")
    result["village"] = address.get("village", "")
    
    # Road information
    result["route_name"] = address.get("road", "")
    result["route_type"] = ""  # Nominatim doesn't separate road type
    
    # Traffic zones - Not available in OSM, keep as None
    result["in_traffic_zone"] = None
    result["in_odd_even_zone"] = None
    
    return result


async def geocode(
    address: str,
    city: str | None = None,
    province: str | None = None,
) -> List[Dict[str, Any]]:
    """Geocode: convert address to coordinates using Nominatim."""
    if not get_settings().osm_enabled:
        return []
    
    # Build query
    query_parts = [address]
    if city:
        query_parts.append(city)
    if province:
        query_parts.append(province)
    query_parts.append(COUNTRY)  # Scoped to Iran, so a Tehran-like name elsewhere cannot win
    
    query = ", ".join(query_parts)
    
    params = {
        "q": query,
        "format": "json",
        "limit": 10,  # Return multiple results
        "addressdetails": 1,
    }
    
    try:
        data = await _make_nominatim_request("/search", params)
    except OsmAPIError:
        return []
    
    if not isinstance(data, list):
        return []
    
    # Convert to the CRM's coordinate spelling: ``lng``, not Nominatim's
    # ``lon``, so every map payload in the app reads the same pair.
    results: List[Dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            results.append({
                "lat": float(item.get("lat", 0)),
                "lng": float(item.get("lon", 0)),
                "display_name": item.get("display_name", ""),
                "address": item.get("address", {}),
                "boundingbox": item.get("boundingbox", []),
                "class": item.get("class", ""),
                "type": item.get("type", ""),
                "importance": item.get("importance", 0),
            })
    
    return results


async def geocode_plus(
    address: str,
    city: str | None = None,
    province: str | None = None,
) -> List[Dict[str, Any]]:
    """Enhanced geocoding for buildings and landmarks.
    
    For OSM, we use the same geocode endpoint but with additional parameters
    to favor precise matches.
    """
    if not get_settings().osm_enabled:
        return []
    
    # Build query with extra precision hints
    query_parts = [address]
    if city:
        query_parts.append(city)
    if province:
        query_parts.append(province)
    query_parts.append(COUNTRY)
    
    query = ", ".join(query_parts)
    
    params = {
        "q": query,
        "format": "json",
        "limit": 10,
        "addressdetails": 1,
        "extratags": 1,
        "namedetails": 1,
    }
    
    try:
        data = await _make_nominatim_request("/search", params)
    except OsmAPIError:
        return []
    
    if not isinstance(data, list):
        return []
    
    # Convert to expected format (same as geocode for now)
    results: List[Dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            results.append({
                "lat": float(item.get("lat", 0)),
                "lng": float(item.get("lon", 0)),
                "display_name": item.get("display_name", ""),
                "address": item.get("address", {}),
                "boundingbox": item.get("boundingbox", []),
                "class": item.get("class", ""),
                "type": item.get("type", ""),
                "importance": item.get("importance", 0),
                "extratags": item.get("extratags", {}),
                "namedetails": item.get("namedetails", {}),
            })
    
    return results


async def get_provinces() -> List[Dict[str, Any]]:
    """Get provinces of Iran using Overpass API."""
    if not get_settings().osm_enabled:
        return []
    
    # Overpass query to get Iranian provinces (admin level 4)
    query = """
    [out:json][timeout:25];
    (
      area["ISO3166-2"="IR"][admin_level=4]->.iran;
      area.iran.admin_level[4];
    );
    out center;
    """
    
    try:
        data = await _make_overpass_request(query)
    except OsmAPIError:
        return []
    
    if not isinstance(data, dict) or "elements" not in data:
        return []
    
    provinces: List[Dict[str, Any]] = []
    for element in data["elements"]:
        if isinstance(element, dict) and element.get("type") in ("node", "area", "relation"):
            tags = element.get("tags", {})
            name = tags.get("name:fa") or tags.get("name") or ""
            if name:
                # Convert to Persian if needed
                provinces.append({
                    "id": element.get("id"),
                    "name": name,
                })
    
    return provinces


async def get_cities_of_province(province_id: Any) -> List[Dict[str, Any]]:
    """Get cities of one province using Overpass API."""
    if not get_settings().osm_enabled:
        return []
    
    # OSM has no stable per-province id a caller could pass back in.
    # We'll need to query by province name instead. This is a limitation.
    # For now, return empty list and rely on the Iran Locations API as primary source.
    # The GIS endpoints will use Iran Locations API as primary, OSM as fallback.
    return []


async def get_administrative_areas() -> Dict[str, Any]:
    """Get the whole province -> county tree, from the node's own gateway.

    OSM has no Iranian province -> county table the way the self-hosted Iran
    Locations dataset does: that relationship lives in overlapping
    ``boundary=administrative`` relations whose nesting has to be resolved
    geometrically. Doing it on every request would be slow and wrong often
    enough to be worse than nothing, so the answer here is the *empty* tree and
    the gateway keeps Iran Locations as its primary source (see
    ``app.api.v1.endpoints.gis.list_cities``).
    """
    return normalize_areas({"provinces": []})


def normalize_areas(payload: Any) -> Dict[str, Any]:
    """Shape a provider payload into the gateway's own area contract.

    ``{"provinces": [{"name": ..., "cities": [...]}], "cities": [...]}`` with
    names normalised and cities deduplicated -- what ``/gis/cities`` hands the
    browser, and what the city picker reads.

    An unrecognised shape yields an *empty* tree rather than raising. The
    endpoint is a filter's option source and its caller already has a documented
    degradation -- an empty tree falls back to the node's own inventory cities.
    Raising would turn a degraded filter into a broken page.
    """
    provinces: List[Dict[str, Any]] = []
    cities: List[str] = []
    seen: set[str] = set()

    rows = payload.get("provinces") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        rows = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _fold_name(row.get("name"))
        if not name:
            continue

        row_cities = row.get("cities")
        if not isinstance(row_cities, list):
            row_cities = []

        folded: List[str] = []
        for city in row_cities:
            if not isinstance(city, dict):
                city = {"name": city}
            city_name = _fold_name(city.get("name"))
            if not city_name:
                continue
            folded.append(city_name)
            if city_name not in seen:
                seen.add(city_name)
                cities.append(city_name)

        provinces.append({"name": name, "cities": folded})

    return {"provinces": provinces, "cities": cities}


def _fold_name(value: Any) -> str:
    """Normalise a place name for the gateway's response."""
    if value is None:
        return ""
    return " ".join(str(value).split())
    
    # Overpass query for Iranian administrative areas
    # This is complex due to OSM structure, so we'll return empty
    # and let the Iran Locations API handle this as primary source
    return {"provinces": []}


async def search_nearby(
    lat: float,
    lng: float,
    layer: str,
    radius_m: int = 1200,
) -> List[Dict[str, Any]]:
    """Search for nearby points of interest using Overpass API."""
    if not get_settings().osm_enabled:
        return []
    
    # Map common layers to OSM amenities
    layer_mapping = {
        "hospital": "amenity=hospital",
        "clinic": "amenity=clinic",
        "pharmacy": "amenity=pharmacy",
        "school": "amenity=school",
        "university": "amenity=university",
        "park": "leisure=park",
        "garden": "leisure=garden",
        "shopping_mall": "shop=mall",
        "market": "shop=market",
        "transit_station": "amenity=transit_station",
        "bus_station": "amenity=bus_station",
        "train_station": "amenity=train_station",
        "metro": "railway=station",
        "gas_station": "amenity=fuel",
        "bank": "amenity=bank",
        "atm": "amenity=atm",
        "post_office": "amenity=post_office",
        "police": "amenity=police",
        "fire_station": "amenity=fire_station",
    }
    
    osm_query = layer_mapping.get(layer, layer)
    if not osm_query:
        return []
    
    # Overpass query for nearby amenities
    query = f"""
    [out:json][timeout:25];
    (
      node[{osm_query}](around:{radius_m},{lat},{lng});
      way[{osm_query}](around:{radius_m},{lat},{lng});
      relation[{osm_query}](around:{radius_m},{lat},{lng});
    );
    out center;
    """
    
    try:
        data = await _make_overpass_request(query)
    except OsmAPIError:
        return []
    
    if not isinstance(data, dict) or "elements" not in data:
        return []
    
    places: List[Dict[str, Any]] = []
    for element in data["elements"]:
        if isinstance(element, dict):
            tags = element.get("tags", {})
            name = tags.get("name") or tags.get("name:fa") or ""
            if name:
                lat_val = element.get("lat") or (element.get("center", {}).get("lat"))
                lng_val = element.get("lon") or (element.get("center", {}).get("lon"))
                if lat_val is not None and lng_val is not None:
                    places.append({
                        "name": str(name),
                        "lat": float(lat_val),
                        "lng": float(lng_val),
                        "tags": tags,
                        "element_type": element.get("type"),
                        "osm_id": element.get("id"),
                    })
    
    return places


async def search_autocomplete(
    term: str,
    lat: float | None = None,
    lng: float | None = None,
) -> List[Dict[str, Any]]:
    """Search for places and addresses using Nominatim."""
    if not get_settings().osm_enabled:
        return []
    
    # Build query
    query_parts = [term, COUNTRY]
    query = ", ".join(query_parts)
    
    params = {
        "q": query,
        "format": "json",
        "limit": 10,
        "addressdetails": 1,
    }
    
    # Add bias if coordinates provided
    if lat is not None and lng is not None:
        params["viewbox"] = f"{lng-0.1},{lat+0.1},{lng+0.1},{lat-0.1}"
        params["bounded"] = 1
    
    try:
        data = await _make_nominatim_request("/search", params)
    except OsmAPIError:
        return []
    
    if not isinstance(data, list):
        return []
    
    items: List[Dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            items.append({
                "title": str(item.get("display_name", "")),
                "address": str(item.get("address", {}).get("road", "")),
                "neighbourhood": str(item.get("address", {}).get("suburb", "")),
                "region": str(item.get("address", {}).get("state", "")),
                "type": str(item.get("type", "")),
                "category": str(item.get("class", "")),
                "lat": float(item.get("lat", 0)),
                "lng": float(item.get("lon", 0)),
            })
    
    return items


async def get_polygons() -> Dict[str, Any]:
    """Get administrative boundary polygons using Overpass API."""
    if not get_settings().osm_enabled:
        return {}
    
    # This is complex and heavy - for now return empty
    # Iran Locations API is the primary source for this
    return {}


async def get_cities_of_province_geometry(province_id: Any) -> List[Dict[str, Any]]:
    """Get counties of one province with boundary WKT."""
    if not get_settings().osm_enabled:
        return []
    
    # Complex query - return empty for now
    return []


async def cached_nominatim_reverse_geocode(
    session,
    latitude: float,
    longitude: float,
    settings=None,
):
    """Cache-first reverse geocode backed by the existing GeoCache grid table.

    The grid keeps the node to one Nominatim call per ~50 m cell (see
    ``app.models.geo_cache``), which is what makes the submission wizard's
    "drop a pin" step affordable: the same block is asked again on every
    listing that lands on it.

    A node with ``osm_enabled=false`` skips the lookup entirely and returns an
    empty district, so the submission still goes through -- a listing with no
    auto-resolved address is usable, one that failed to submit is not.
    """
    from datetime import timedelta

    from sqlmodel import select

    from app.models.base import utcnow
    from app.models.geo_cache import CACHE_TTL_DAYS, GeoCache, grid_center, grid_key

    s = settings or get_settings()
    if not s.osm_enabled:
        return {}

    key = grid_key(latitude, longitude)
    cutoff = utcnow() - timedelta(days=CACHE_TTL_DAYS)

    row = (await session.exec(select(GeoCache).where(GeoCache.grid_key == key))).first()
    if row is not None and row.fetched_at >= cutoff:
        # The cached columns are the administrative ones; the traffic-zone flags
        # are per-pin metadata the table does not store, so a hit reports them as
        # "not said" rather than inventing a fresh call to recover them.
        return {
            "province": row.province,
            "city": row.city,
            "district": row.district,
            "neighborhood": row.neighborhood,
            "display_name": row.display_name,
            "formatted_address": row.display_name,
            "municipality_zone": "",
            "in_traffic_zone": None,
            "in_odd_even_zone": None,
        }

    center_lat, center_lng = grid_center(latitude, longitude)
    fields = await _query_osm_safe(center_lat, center_lng)

    if row is None:
        row = GeoCache(grid_key=key, latitude=center_lat, longitude=center_lng)
    row.province = fields.get("province", row.province or "")
    row.city = fields.get("city", row.city or "")
    row.district = fields.get("district", row.district or "")
    row.neighborhood = fields.get("neighborhood", row.neighborhood or "")
    row.display_name = fields.get("display_name", row.display_name or "")
    row.fetched_at = utcnow()
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return {
        "province": row.province,
        "city": row.city,
        "district": row.district,
        "neighborhood": row.neighborhood,
        "display_name": row.display_name,
        "formatted_address": fields.get("formatted_address") or row.display_name,
        "municipality_zone": fields.get("municipality_zone", ""),
        "in_traffic_zone": fields.get("in_traffic_zone"),
        "in_odd_even_zone": fields.get("in_odd_even_zone"),
    }


async def _query_osm_safe(latitude: float, longitude: float) -> Dict[str, Any]:
    """One OSM call, degrading to empty on any failure (offline-first)."""
    try:
        return await reverse_geocode(latitude, longitude)
    except Exception as exc:
        logger.warning("osm unavailable (%s); keeping empty geocode", exc)
        return {}