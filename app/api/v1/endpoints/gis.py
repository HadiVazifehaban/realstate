"""GIS endpoints for OpenStreetMap integration.

Every OSM call the browser needs (Nominatim reverse/geocoding, Overpass nearby
POI) is proxied through the node, so the endpoints stay behind the same
principal gate as the rest of the data-bearing surface and the node can cache
aggressively without the browser knowing it did.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import SessionDep, SettingsDep, get_principal
from app.services import iran_locations, osm_service
from app.services.osm_service import OsmAPIError

# GIS endpoints are read-only and don't require authentication for public access
router = APIRouter()


@router.get("/reverse")
async def reverse_geocode(
    lat: float,
    lng: float,
    session: SessionDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    """Convert point to address using OSM Nominatim reverse geocoding.

    Cache-first: the grid in ``app.models.geo_cache`` holds one row per ~50 m
    cell, so dropping a pin on the same block twice costs one upstream call.
    """
    result = await osm_service.cached_nominatim_reverse_geocode(
        session, lat, lng, settings
    )
    return result


@router.get("/geocode")
async def geocode(
    address: str,
    city: str | None = None,
    province: str | None = None,
) -> dict[str, Any]:
    """Convert address to coordinates using OSM Nominatim."""
    try:
        items = await osm_service.geocode(address, city, province)
        return {"items": items}
    except OsmAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "osm_api_error", "message": str(e)},
        ) from e


@router.get("/geocode/plus")
async def geocode_plus(
    address: str,
    city: str | None = None,
    province: str | None = None,
) -> dict[str, Any]:
    """Enhanced geocoding for buildings and landmarks using OSM Nominatim."""
    try:
        items = await osm_service.geocode_plus(address, city, province)
        return {"items": items}
    except OsmAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "osm_api_error", "message": str(e)},
        ) from e


@router.get(
    "/cities",
    summary="Provinces and cities, for the cascading city filter (فیلتر)",
)
async def list_cities() -> dict[str, Any]:
    """Provinces and their cities, ready to drive a dependent dropdown.

    The province -> city cascade of the listing filter reads its options from
    here, which is why the name list is normalized and deduplicated server-side
    rather than by the browser: every client would otherwise re-derive the same
    shape from a payload the provider has shipped in more than one layout.

    Provider order is the self-hosted Iran Locations container first -- it needs
    no platform key and answers from a local dataset -- then OSM. When both
    come back empty the client falls back to the node's own inventory cities.
    """
    tree = await iran_locations.fetch_areas_tree()
    if tree.get("provinces"):
        return tree

    payload = await osm_service.get_administrative_areas()
    return osm_service.normalize_areas(payload)


@router.get(
    "/nearby",
    summary="Named amenities within a radius (مکان‌های نزدیک) - فارسی",
)
async def nearby_places(
    lat: float,
    lng: float,
    layer: str,
    radius_m: int = 1200,
) -> dict[str, Any]:
    """Places of one OSM category around a point.

    ``layer`` is one of OSM's amenity classes (park, hospital, school, etc.).
    The returned ``farsi_title`` is theirs too, so the UI shows their wording
    rather than a re-translated one. ``distance`` is straight-line distance,
    since OSM/Overpass does not provide travel distance, only straight-line.
    """
    try:
        places = await osm_service.search_nearby(lat, lng, layer, radius_m)
    except OsmAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "osm_api_error", "message": str(e)},
        ) from e
    return {"layer": layer, "places": places}


@router.get(
    "/search",
    summary="Place/address autocomplete (جستجوی مکان‌مبنا) - فارسی",
)
async def search_places(
    term: str,
    lat: float | None = None,
    lng: float | None = None,
) -> dict[str, Any]:
    """Free-text place search, for the submission form's address field.

    Uses OSM Nominatim for place/address autocomplete. Results are ranked by
    distance from the reference point if provided.
    """
    if not term.strip():
        return {"items": []}
    try:
        items = await osm_service.search_autocomplete(term, lat, lng)
    except OsmAPIError as e:
        # A 400 from a missing reference point is the caller's mistake, not an
        # upstream outage, so it is surfaced as such.
        status_code = (
            status.HTTP_400_BAD_REQUEST
            if e.status_code == 400
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(
            status_code=status_code,
            detail={"error": "osm_api_error", "message": str(e)},
        ) from e
    return {"items": items}


@router.get(
    "/areas",
    summary="Province -> county tree (استان‌ها و شهرها) - فارسی",
)
async def get_administrative_areas() -> dict[str, Any]:
    """The whole administrative tree, from OSM/Overpass.

    Fanned out per province for the county lists, so this is one slow response
    and the cache makes it cheap to repeat. ``/gis/cities`` is the flattened,
    ready-to-render form the listing filter uses.
    """
    try:
        return await osm_service.get_administrative_areas()
    except OsmAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "osm_api_error", "message": str(e)},
        ) from e


@router.get("/polygons")
async def get_polygons() -> dict[str, Any]:
    """Get administrative boundaries polygons from OSM."""
    try:
        return await osm_service.get_polygons()
    except OsmAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "osm_api_error", "message": str(e)},
        ) from e


@router.get(
    "/static-map",
    summary="Static map image bytes, used by node-internal renderers - فارسی",
    status_code=status.HTTP_502_BAD_GATEWAY,
    responses={502: {"description": "OSM serves raster tiles, not a per-pin image."}},
)
async def get_static_map(
    lat: float,
    lng: float,
    width: int = 600,
    height: int = 400,
    zoom: int = 15,
) -> None:
    """Stream a rendered OSM static map back to the caller.

    There is nothing to stream: OSM serves raster tiles, and the browser draws
    them itself from ``NEXT_PUBLIC_TILE_URL``. A per-pin image needs a renderer
    this node does not run, and inventing a blank PNG would show a grey box on
    a shared listing with nothing to explain it. So the route answers with the
    tile URL template a caller should switch to instead.

    The route stays mounted on purpose: every client built against the previous
    contract calls it, and a 404 reads as "this endpoint moved" rather than
    "this approach is gone".
    """
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={
            "error": "static_map_not_available",
            "message": "OSM does not provide static map images. Use the node's raster tile layer.",
            "tile_url_template": "/tile/{z}/{x}/{y}.png",
        },
    )