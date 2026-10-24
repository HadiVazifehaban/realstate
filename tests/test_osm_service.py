"""Tests for the OpenStreetMap GIS gateway (Nominatim + Overpass).

Upstream is never contacted: every call is intercepted, so nothing spends a
public-service request budget. What is asserted is what a pure-OSM migration
could plausibly get wrong -- that the payload lands in the CRM's own fields,
that the coordinate order is right, and that the node degrades instead of
raising when a remote call fails.
"""

from __future__ import annotations

import inspect

import pytest

from app.services import osm_service
from app.services.osm_service import OsmAPIError


@pytest.fixture(autouse=True)
def _no_upstream(monkeypatch):
    """Block every transport, then let a test install its own."""
    import app.services.osm_service as mod

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

    monkeypatch.setattr(mod.httpx, "AsyncClient", _Blocked)
    yield


# --------------------------------------------------- reverse geocoding shape
class _FakeGeoCache:
    """The one row the grid table would hold for a cell."""

    def __init__(self) -> None:
        self.province = ""
        self.city = ""
        self.district = ""
        self.neighborhood = ""
        self.display_name = ""
        self.grid_key = ""
        self.latitude = 0.0
        self.longitude = 0.0
        self.fetched_at = None


class _FakeSession:
    """Stands in for the AsyncSession the cache path needs.

    ``exec`` always reports "no cached row", which is the path that exercises
    the upstream mapping instead of the cache read.
    """

    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def add(self, row: object) -> None:
        self.added.append(row)

    async def exec(self, *a, **kw):
        return self

    def first(self):
        return None

    async def commit(self):
        self.commits += 1

    async def refresh(self, row):
        return None


async def test_reverse_geocode_maps_the_documented_fields(monkeypatch) -> None:
    """Nominatim's nested ``address`` object lands in the CRM's flat fields."""

    async def _fake_reverse(lat, lng):
        return osm_service_reverse_fields()

    # Patch the *inner* helper the cache writes from, so the mapping the cache
    # reads (province / city / neighbourhood) is what the test controls.
    monkeypatch.setattr(osm_service, "reverse_geocode", _fake_reverse)
    monkeypatch.setattr(
        osm_service,
        "_query_osm_safe",
        lambda lat, lng: _await(osm_service_reverse_fields()),
    )

    result = await osm_service.cached_nominatim_reverse_geocode(_FakeSession(), 35.71, 51.34)

    assert result["province"] == "تهران"
    assert result["city"] == "تهران"
    assert result["neighborhood"] == "سعادت‌آباد"
    assert result["formatted_address"].startswith("تهران")


def osm_service_reverse_fields() -> dict:
    """The flat field set the real ``reverse_geocode`` produces for a Tehran pin."""
    return {
        "formatted_address": "تهران, سعادت‌آباد, میدان ۳۳, ایران",
        "neighbourhood": "سعادت‌آباد",
        "neighborhood": "سعادت‌آباد",
        "municipality_zone": "منطقه ۱",
        "city": "تهران",
        "state": "تهران",
        "province": "تهران",
        "district": "شهرستان تهران",
        "region": "",
        "place": "",
        "village": "",
        "route_name": "خیابان سرو",
        "route_type": "",
        "in_traffic_zone": None,
        "in_odd_even_zone": None,
    }


def _await(value):
    """Wrap a value so it can stand in for an ``await``-ed coroutine result."""
    async def _inner():
        return value
    return _inner()


async def test_reverse_geocode_tolerates_a_bare_payload(monkeypatch) -> None:
    """A sparse Nominatim answer must not raise or invent a district."""

    async def _empty(lat, lng):
        return {}

    monkeypatch.setattr(osm_service, "_query_osm_safe", lambda lat, lng: _await({}))

    result = await osm_service.cached_nominatim_reverse_geocode(_FakeSession(), 0.0, 0.0)

    assert result["city"] == ""
    assert result["province"] == ""
    assert result["display_name"] == ""


async def test_reverse_geocode_never_reads_a_nonexistent_wrapper() -> None:
    """Nominatim answers the coordinate object, not a response envelope.

    The previous provider's reverse-geocoding payload arrived nested under a
    ``formatted_address`` wrapper, so reading that key off Nominatim's response
    -- which has no such key -- would silently yield an empty district for
    every reverse call.
    """
    source = inspect.getsource(osm_service.reverse_geocode)
    assert "data.get(\"address\"" in source
    assert "formatted_address" in source


async def test_reverse_geocode_degrades_when_service_disabled() -> None:
    """``osm_enabled=false`` means an empty district, not a failed submission."""
    from app.core.config import Settings

    class _Session:
        async def exec(self, *a, **kw):
            raise AssertionError("no cache read expected")

        async def commit(self):
            raise AssertionError("no cache write expected")

    result = await osm_service.cached_nominatim_reverse_geocode(
        _Session(), 35.71, 51.34, Settings(OSM_ENABLED=False)
    )

    assert result == {}


async def test_reverse_geocode_safe_never_raises(monkeypatch) -> None:
    """A broken upstream leaves the geocode empty instead of killing the submit."""

    async def _boom(lat, lng):
        raise OsmAPIError("nominatim is down")

    monkeypatch.setattr(osm_service, "reverse_geocode", _boom)

    result = await osm_service.cached_nominatim_reverse_geocode(_FakeSession(), 35.71, 51.34)

    assert result["province"] == ""
    assert result["city"] == ""


# --------------------------------------------------- geocoding shape
async def test_geocode_returns_items_list(monkeypatch) -> None:
    """``/gis/geocode`` answers ``{items: [...]}``; the service returns the list.

    Both ``lat`` and ``lon`` are read straight from Nominatim's payload: a swap
    draws the listing in the sea.
    """

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "lat": "35.6892",
                    "lon": "51.3890",
                    "display_name": "تهران, ایران",
                    "address": {"city": "تهران"}
                }
            ]

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None, **kw):
            assert "nominatim.openstreetmap.org/search" in url
            assert params["q"] == "سعادت‌آباد, تهران, تهران, ایران"
            assert params["format"] == "json"
            return _Response()

    monkeypatch.setattr(osm_service.httpx, "AsyncClient", _Client)

    items = await osm_service.geocode("سعادت‌آباد", city="تهران", province="تهران")

    assert [item["lat"] for item in items] == [35.6892]
    assert [item["lng"] for item in items] == [51.3890]
    assert "lon" not in items[0]
    assert items[0]["lng"] == 51.3890


async def test_geocode_plus_returns_items_list(monkeypatch) -> None:
    """The plus variant asks for the extra tag details, same item shape."""

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "lat": "35.7",
                    "lon": "51.4",
                    "display_name": "پلاک ۱۲, تهران",
                    "address": {},
                    "extratags": {},
                    "namedetails": {}
                }
            ]

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None, **kw):
            assert params["extratags"] == 1
            return _Response()

    monkeypatch.setattr(osm_service.httpx, "AsyncClient", _Client)

    items = await osm_service.geocode_plus("پلاک ۱۲", city="تهران")

    assert len(items) == 1
    assert items[0]["display_name"] == "پلاک ۱۲, تهران"


# --------------------------------------------------- nearby / Overpass
async def test_search_nearby_reads_osm_tags(monkeypatch) -> None:
    """Overpass elements are read as ``lat``/``lon`` -- a swap draws Iran at sea."""

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "elements": [
                    {
                        "type": "node",
                        "id": 1,
                        "lat": 35.7118,
                        "lon": 51.3422,
                        "tags": {"amenity": "park", "name": "بوستان لاله"}
                    },
                    # A way carries no lat/lon of its own; the centre block does.
                    {
                        "type": "way",
                        "id": 2,
                        "center": {"lat": 35.8, "lon": 51.5},
                        "tags": {"amenity": "park", "name": "بوستان بزرگ"}
                    },
                    # Unnamed features carry no signal for a buyer-facing list.
                    {"type": "node", "id": 3, "lat": 35.1, "lon": 51.1, "tags": {"amenity": "park"}}
                ]
            }

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, data=None, **kw):
            assert "overpass-api.de" in url
            assert data["data"].strip().startswith("[out:json]")
            return _Response()

    monkeypatch.setattr(osm_service.httpx, "AsyncClient", _Client)

    places = await osm_service.search_nearby(35.71, 51.34, "park", 1200)

    assert [p["name"] for p in places] == ["بوستان لاله", "بوستان بزرگ"]
    assert places[0]["lat"] == 35.7118
    assert places[0]["lng"] == 51.3422
    # The `out center;` clause is what makes ways use their centre.
    assert places[1]["lat"] == 35.8


async def test_search_nearby_maps_the_layer_to_an_osm_tag(monkeypatch) -> None:
    """A bucket layer like ``hospital`` becomes ``amenity=hospital`` upstream."""

    seen: dict = {}

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"elements": []}

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, data=None, **kw):
            seen["data"] = data["data"]
            return _Response()

    monkeypatch.setattr(osm_service.httpx, "AsyncClient", _Client)

    await osm_service.search_nearby(35.71, 51.34, "hospital", 500)

    assert "node[amenity=hospital]" in seen["data"]
    assert "around:500,35.71,51.34" in seen["data"]


# --------------------------------------------------- errors carry upstream status
async def test_http_error_is_raised_as_api_error(monkeypatch) -> None:
    """An upstream 5xx is logged, and the route-facing error carries the status.

    ``geocode`` swallows the error and returns an empty list so the browser
    keeps a working map, but the typed error it swallowed still carries the
    upstream status for the endpoint layer that needs to translate it.
    """

    class _Response:
        status_code = 503
        text = "upstream down"

        def raise_for_status(self):
            import httpx

            raise httpx.HTTPStatusError(
                "503", request=httpx.Request("GET", "x"), response=self
            )

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **kw):
            return _Response()

    monkeypatch.setattr(osm_service.httpx, "AsyncClient", _Client)

    # The public call degrades rather than propagating.
    assert await osm_service.geocode("تهران") == []

    # The transport-level error, however, carries the upstream status through.
    with pytest.raises(OsmAPIError) as exc:
        await osm_service._make_nominatim_request("/search", {"q": "تهران"})
    assert exc.value.status_code == 503


async def test_transport_error_wraps_connection_failures(monkeypatch) -> None:
    """A reset connection is an OsmAPIError, not a raw httpx exception."""

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **kw):
            raise RuntimeError("connection reset")

    monkeypatch.setattr(osm_service.httpx, "AsyncClient", _Client)

    with pytest.raises(OsmAPIError):
        await osm_service._make_nominatim_request("/search", {"q": "تهران"})


async def test_geocode_degrades_to_empty_on_error(monkeypatch) -> None:
    """The service call itself never raises -- offline-first means empty, not 500."""

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **kw):
            raise RuntimeError("connection reset")

    monkeypatch.setattr(osm_service.httpx, "AsyncClient", _Client)

    assert await osm_service.geocode("تهران") == []


# --------------------------------------------------- the enabled gate
async def test_every_entry_point_is_gated_on_osm_enabled(monkeypatch) -> None:
    """A node with ``osm_enabled=false`` must never build a request."""
    from app.core.config import Settings

    monkeypatch.setattr(osm_service, "get_settings", lambda: Settings(OSM_ENABLED=False))
    monkeypatch.setattr(osm_service, "_make_nominatim_request", _boom)
    monkeypatch.setattr(osm_service, "_make_overpass_request", _boom_async)

    assert await osm_service.geocode("تهران") == []
    assert await osm_service.geocode_plus("پلاک ۱۲") == []
    assert await osm_service.search_nearby(35.7, 51.4, "park") == []
    assert await osm_service.search_autocomplete("تهران") == []
    assert await osm_service.reverse_geocode(35.7, 51.4) == {}
    assert await osm_service.get_administrative_areas() == {
        "provinces": [],
        "cities": []
    }


async def _boom(*a, **kw):
    raise AssertionError("a disabled node must not call upstream")


async def _boom_async(*a, **kw):
    raise AssertionError("a disabled node must not call upstream")


# --------------------------------------------------- settings hygiene
def test_no_api_key_anywhere_in_settings() -> None:
    """OSM runs on free public services: there is nothing to provision."""
    from app.core.config import Settings

    fields = Settings.model_fields
    assert not any("neshan" in name.lower() for name in fields)
    assert not any(name.lower().endswith("api_key") for name in fields)
    # No NEXT_PUBLIC_ counterpart either -- nothing secret can be shipped.
    assert not any(name.startswith("next_public_") for name in fields)


def test_nominatim_and_overpass_endpoints_are_configured() -> None:
    from app.core.config import Settings

    fields = Settings.model_fields
    assert "nominatim_base_url" in fields
    assert "overpass_endpoint" in fields
    assert "osm_enabled" in fields


def test_static_map_generation_is_absent() -> None:
    """OSM serves raster tiles, not a per-pin image: the old fetcher is gone."""
    assert not hasattr(osm_service, "fetch_static_map_image")
    assert not hasattr(osm_service, "generate_static_map_image_url")


# --------------------------------------------------- area normalization
def test_normalize_areas_shapes_the_gateway_contract() -> None:
    """A provider payload becomes the tree the city picker reads."""
    result = osm_service.normalize_areas(
        {"provinces": [{"name": " آذربایجان شرقی ", "cities": [{"name": "تبریز"}, "مراغه", "تبریز"]}]}
    )
    assert result["provinces"] == [
        {"name": "آذربایجان شرقی", "cities": ["تبریز", "مراغه", "تبریز"]}
    ]
    # The flat list is deduplicated, so the picker's fallback pool has no doubles.
    assert result["cities"] == ["تبریز", "مراغه"]


def test_normalize_areas_degrades_instead_of_raising() -> None:
    """A shape this node cannot read yields an empty tree, not a 500.

    The endpoint's caller falls back to the node's own inventory cities on an
    empty tree; a raised error would turn a degraded filter into a broken page.
    """
    for payload in (None, "nonsense", {}, {"provinces": "nope"}, {"provinces": [1, 2]}):
        assert osm_service.normalize_areas(payload) == {"provinces": [], "cities": []}
