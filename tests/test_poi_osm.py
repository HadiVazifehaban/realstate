"""The POI enrichment path, now served by OpenStreetMap.

Outside is never contacted: every call is intercepted, so nothing spends a
public-service request budget. What is asserted is what the migration could
plausibly get wrong -- that the local tiles database stays the primary source,
that the OSM fallback only fires when it is genuinely unavailable, and that a
POI outage costs a page its amenities block rather than its render.
"""

from __future__ import annotations

import inspect

import pytest

from app.services import osm_service, poi_service
from app.core.config import Settings


def _settings(**overrides) -> Settings:
    base = dict(
        OVERPASS_ENDPOINT="http://invalid",
        OSM_ENABLED=True,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture(autouse=True)
def _no_upstream(monkeypatch):
    """Block every transport, then let a test install its own."""
    import app.services.osm_service as osm_mod

    class _Blocked:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **kw):
            raise AssertionError("test must not reach nominatim.openstreetmap.org")

        async def post(self, *a, **kw):
            raise AssertionError("test must not reach the Overpass API")

    monkeypatch.setattr(osm_mod.httpx, "AsyncClient", _Blocked)
    yield


# ------------------------------------------------------------ bucket mapping
def test_every_bucket_maps_to_at_least_one_layer() -> None:
    """A bucket that forgot its layers would render permanently empty."""
    assert set(poi_service.NEARBY_LAYERS) == set(poi_service.BUCKETS)
    for bucket, layers in poi_service.NEARBY_LAYERS.items():
        assert layers, f"{bucket} has no OSM layer"


def test_layers_are_distinct_across_buckets() -> None:
    """The same layer answering two buckets double-fetches upstream quota."""
    all_layers = [layer for layers in poi_service.NEARBY_LAYERS.values() for layer in layers]
    assert len(all_layers) == len(set(all_layers))


def test_buckets_still_cover_the_buyer_facing_amenities() -> None:
    """The migration must not silently narrow what a buyer sees.

    The old Overpass selectors covered transport, shops, schools, hospitals
    and parks; the layer lists must cover the same intent with OSM's own
    amenity names.
    """
    assert {"formal_school", "university"} <= set(poi_service.NEARBY_LAYERS["education"])
    assert {"hospital", "clinic"} <= set(poi_service.NEARBY_LAYERS["healthcare"])
    assert {"park"} <= set(poi_service.NEARBY_LAYERS["leisure"])
    assert len(poi_service.NEARBY_LAYERS["transport"]) >= 3


# ------------------------------------------------------------ bucket grouping
def test_bucket_of_places_an_osm_node_in_the_right_bucket() -> None:
    """An OSM amenity tag is grouped by the same buckets the page renders."""
    by_tag = {
        "amenity": "hospital",
    }
    assert poi_service._bucket_of(by_tag) == "healthcare"
    assert poi_service._bucket_of({"amenity": "school"}) == "education"
    assert poi_service._bucket_of({"amenity": "bus_station"}) == "transport"
    assert poi_service._bucket_of({"shop": "supermarket"}) == "shopping"
    assert poi_service._bucket_of({"leisure": "park"}) == "leisure"
    # A landmark or a bench carries no bucket.
    assert poi_service._bucket_of({"tourism": "artwork"}) is None


def test_overpass_parse_drops_unnamed_and_unplaced() -> None:
    """An unnamed or unplaced node is noise in a buyer-facing list."""
    payload = {
        "elements": [
            {"lat": 35.72, "lon": 51.34, "tags": {"leisure": "park", "name": "بوستان لاله"}},
            {"lat": 35.72, "lon": 51.34, "tags": {"leisure": "park"}},
            {"tags": {"leisure": "park", "name": "بدون مختصات"}},
            {"lat": 0.0, "lon": 0.0, "tags": {"tourism": "artwork", "name": "مجسمه"}}
        ]
    }

    buckets = poi_service._parse_overpass(payload)

    assert [p["name"] for p in buckets["leisure"]] == ["بوستان لاله"]


def test_park_can_arrive_as_either_amenity_or_leisure() -> None:
    """OSM tags a park as ``leisure=park``, but a few carry ``amenity`` too.

    The bucket mapping reads the tag the tile database actually writes, so a
    park that arrives tagged ``amenity=park`` must still land in the leisure
    bucket rather than being dropped from the page.
    """
    payload = {
        "elements": [
            {"lat": 35.7, "lon": 51.3, "tags": {"leisure": "park", "name": "بوستان الف"}},
            {"lat": 35.71, "lon": 51.31, "tags": {"amenity": "park", "name": "بوستان ب"}}
        ]
    }

    buckets = poi_service._parse_overpass(payload)

    names = {p["name"] for p in buckets["leisure"]}
    assert "بوستان الف" in names
    assert "بوستان ب" in names


# ------------------------------------------------------ tiles database is primary
async def test_tiles_database_is_queried_before_any_http_call(monkeypatch) -> None:
    """The node's own PostGIS answers first; a POI lookup costs no egress."""
    calls: list[str] = []

    async def _tiles(lat, lng, radius_m):
        calls.append("tiles")
        return {key: [] for key in poi_service.BUCKETS}

    async def _osm_boom(*a, **kw):
        calls.append("osm")
        raise AssertionError("OSM must not be called when the tiles DB answers")

    monkeypatch.setattr(poi_service, "nearby_pois_from_tiles", _tiles)
    monkeypatch.setattr(osm_service, "search_nearby", _osm_boom)

    buckets = await poi_service.fetch_nearby(35.71, 51.34, 1200, _settings())

    assert calls == ["tiles"]
    assert buckets == {key: [] for key in poi_service.BUCKETS}


async def test_fetch_nearby_falls_back_to_osm_when_tiles_unreachable(monkeypatch) -> None:
    """The tiles DB is internal and can be down; the page still gets amenities.

    One Overpass call per bucket layer: the layers are the contract with the
    page, so a failure on one bucket must not take the other four down.
    """
    calls: list[str] = []

    async def _tiles_boom(lat, lng, radius_m):
        calls.append("tiles")
        raise RuntimeError("connection refused")

    async def _osm(lat, lng, layer, radius_m=1200):
        calls.append(f"osm:{layer}")
        return []

    monkeypatch.setattr(poi_service, "nearby_pois_from_tiles", _tiles_boom)
    monkeypatch.setattr(osm_service, "search_nearby", _osm)

    buckets = await poi_service.fetch_nearby(35.71, 51.34, 1200, _settings())

    assert calls[0] == "tiles"
    # One call per configured layer across every bucket.
    expected_layers = [layer for layers in poi_service.NEARBY_LAYERS.values() for layer in layers]
    assert calls[1:] == [f"osm:{layer}" for layer in expected_layers]
    assert buckets == {key: [] for key in poi_service.BUCKETS}


async def test_osm_failure_yields_empty_buckets_not_a_crash(monkeypatch) -> None:
    """A POI outage costs a page its amenities block, not its render."""

    async def _tiles_boom(lat, lng, radius_m):
        raise RuntimeError("connection refused")

    async def _boom(lat, lng, layer, radius_m=1200):
        raise osm_service.OsmAPIError("429 RateLimited", status_code=429)

    monkeypatch.setattr(poi_service, "nearby_pois_from_tiles", _tiles_boom)
    monkeypatch.setattr(osm_service, "search_nearby", _boom)

    buckets = await poi_service.fetch_nearby(35.71, 51.34, 1200, _settings())

    assert buckets == {key: [] for key in poi_service.BUCKETS}


def test_no_neshan_left_in_the_poi_path() -> None:
    """The migration is complete: nothing in the path may still name the vendor."""
    import app.services.poi_service as mod

    source = inspect.getsource(mod)
    assert "neshan" not in source.lower()


def test_no_travel_distance_is_used_for_ordering() -> None:
    """Overpass has no travel distance; ordering is recomputed from the pin.

    The old path ordered by the vendor's ``distance`` (travel, not straight
    line), which could exceed the search radius and quietly dropped nearer
    places. The new path must not depend on any such field.
    """
    import app.services.poi_service as mod

    source = inspect.getsource(mod)
    assert "travel_distance" not in source


def test_poi_service_still_parses_overpass_into_buckets() -> None:
    """The Overpass parser, shared with the tiles row shape, is still wired."""
    import app.services.poi_service as mod

    assert hasattr(mod, "_parse_overpass")
    assert set(mod.BUCKETS) == {
        "transport",
        "shopping",
        "education",
        "healthcare",
        "leisure"
    }


def test_bucket_of_covers_every_bucket_it_can_name() -> None:
    """Each rendered bucket is reachable from at least one real OSM tag."""
    reachable = set()
    for tags in (
        {"amenity": "bus_station"},
        {"shop": "mall"},
        {"amenity": "school"},
        {"amenity": "hospital"},
        {"leisure": "park"}
    ):
        reachable.add(poi_service._bucket_of(tags))
    assert reachable <= set(poi_service.BUCKETS)
    assert len(reachable) == len(poi_service.BUCKETS)
