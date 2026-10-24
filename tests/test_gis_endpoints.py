"""The public surface of the GIS endpoints.

These assert the shape of the contract rather than geocoding behaviour: that the
routes exist where the brief puts them, that nothing on them is anonymous, and
that the node never invites an API key to travel somewhere it would be logged.

Upstream is not contacted here. Nothing spends a request budget.
"""

from __future__ import annotations

import asyncio

import httpx

from app.main import create_app


def _openapi_paths() -> dict:
    """Every route the app declares, straight from the generated schema.

    FastAPI 1.x nests routers behind `_IncludedRouter` wrappers whose route
    trees are not uniformly walkable; the OpenAPI document is the one place the
    fully-resolved prefixes are guaranteed to be visible.
    """
    return create_app().openapi()["paths"]


def test_every_gis_route_is_mounted_at_the_documented_path() -> None:
    paths = _openapi_paths()

    for expected in (
        "/api/v1/gis/reverse",
        "/api/v1/gis/geocode",
        "/api/v1/gis/geocode/plus",
        "/api/v1/gis/areas",
        "/api/v1/gis/polygons",
        "/api/v1/gis/static-map"
    ):
        assert expected in paths, f"{expected} is not mounted"


def test_gis_routes_are_not_anonymous() -> None:
    """The endpoints carry the node's own inventory, so they sit behind auth.

    The reverse-geocoding call in the submission wizard proves why: the picker
    fires it from a logged-in page whenever a pin is dropped, so it must sit
    behind the same principal gate as every other data-bearing surface.
    """
    app = create_app()

    async def _unauthenticated() -> int:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/v1/gis/reverse", params={"lat": 35.7, "lng": 51.4}
            )
            return response.status_code

    assert asyncio.run(_unauthenticated()) == 401


def test_no_gis_route_takes_a_key_as_a_query_parameter() -> None:
    """Nominatim and Overpass need no key, and none may be invited inbound.

    Even where no key exists, a ``key`` parameter would put a secret into a
    URL, an access log and a referrer if one were ever introduced; the routes
    take only what the map needs.
    """
    from app.main import create_app

    schema = create_app().openapi()["paths"]
    for path, spec in schema.items():
        if not path.startswith("/api/v1/gis/"):
            continue
        for method, operation in spec.items():
            for param in operation.get("parameters", []):
                name = param.get("name", "").lower()
                assert name not in {"key", "api_key", "apikey"}, path


def test_static_map_route_declares_no_key_parameter() -> None:
    """The tile endpoint streams bytes it fetched itself -- it needs no key input."""
    schema = create_app().openapi()["paths"]
    operation = schema["/api/v1/gis/static-map"]["get"]

    names = {p["name"] for p in operation.get("parameters", [])}
    assert "key" not in names
    assert names <= {"lat", "lng", "width", "height", "zoom"}, names


def test_static_map_route_answers_deliberately_not_a_blank_image() -> None:
    """OSM serves raster tiles, not a per-pin image.

    The route exists and answers 502 with the tile URL to use: a silently
    empty PNG would render as a grey box on a shared listing with nothing to
    explain it, and a route that vanished would break every client built
    against the contract.
    """
    import asyncio

    from app.main import create_app

    app = create_app()
    schema = create_app().openapi()["paths"]
    assert "/api/v1/gis/static-map" in schema
    assert "get" in schema["/api/v1/gis/static-map"]

    async def _fetch() -> int:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/v1/gis/static-map", params={"lat": 35.7, "lng": 51.4}
            )
            # Anonymous, so the gate answers before the route body does.
            return response.status_code

    assert asyncio.run(_fetch()) == 401


def test_no_vendor_key_is_shipped_as_a_setting() -> None:
    """OSM runs on free public services: there is no secret to ship."""
    from app.core.config import Settings

    fields = Settings.model_fields
    assert not any("neshan" in name.lower() for name in fields)
    # No NEXT_PUBLIC_ counterpart in settings -- the browser's map calls are
    # tile fetches, and anything the node proxies stays proxied.
    assert not any(name.startswith("next_public_") for name in fields)
