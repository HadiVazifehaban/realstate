"""Sheypoor ingestion source: client, search params, unified-schema parser."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.models.enums import DealType, PropertyType  # noqa: E402
from app.services.scraper.sheypoor_client import SheypoorClient  # noqa: E402
from app.services.scraper.sheypoor_parser import (  # noqa: E402
    parse_sheypoor_detail,
    parse_sheypoor_search,
)
from app.services.scraper.sheypoor_taxonomy import build_search_params  # noqa: E402

TEST_SETTINGS = Settings(
    database_url="sqlite+aiosqlite://",
    scraper_pace_min_seconds=0.0,
    scraper_pace_max_seconds=0.0,
    scraper_base_backoff_seconds=1.0,
)


def _run(coro):
    """Run a coroutine on a dedicated loop (see test_phase2_ingestion)."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    @property
    def text(self):
        """Raw body, as the detail-page path needs it.

        A str payload is treated as HTML so the detail tests can pass a literal
        page fragment instead of hand-rolling a response object.
        """
        return self._payload if isinstance(self._payload, str) else ""


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs.get("params")))
        return self._responses.pop(0)


# --------------------------------------------------------------- search params


def test_search_sends_the_verified_api_params() -> None:
    """Sheypoor's live search takes a category *id*, not a Divar-style slug.

    These params were read off the working endpoint on 2026-10-05; the previous
    ``/api/web/v1/...`` client sent ``f=buy`` and answered 404 for every job.
    """
    params = build_search_params("Tehran", "houses-apartments-for-sale", page=1)
    assert params == {"location": "tehran", "category": "43604", "p": "1"}


def test_search_page_is_one_based() -> None:
    assert build_search_params("iran", "land", page=3)["p"] == "3"
    # A zero/negative page would silently return page 1 forever.
    assert build_search_params("iran", "land", page=0)["p"] == "1"


def test_search_rejects_a_category_with_no_id() -> None:
    with pytest.raises(ValueError):
        build_search_params("iran", "atlantis")


def test_search_hits_the_verified_api_endpoint() -> None:
    async def _inner():
        client = SheypoorClient(settings=TEST_SETTINGS)
        client._session = _FakeSession([_FakeResponse({"data": []})])
        await client.search("iran", "houses-apartments-for-sale", 1)
        return client._session.calls[0]

    method, url, params = _run(_inner())
    assert method == "GET"
    assert url.endswith("/api/v10.0.0/search")
    assert params["category"] == "43604"
    assert params["location"] == "iran"


def test_search_ignores_districts_instead_of_pretending_to_honour_them() -> None:
    """Sheypoor has no district filter here; silently widening to the whole
    country would be worse than the caller knowing the narrowing was dropped."""

    async def _inner():
        client = SheypoorClient(settings=TEST_SETTINGS)
        client._session = _FakeSession([_FakeResponse({"data": []})])
        await client.search("iran", "land", 1, districts=["saat-abad"])
        return client._session.calls[0]

    _, _, params = _run(_inner())
    assert "neighborhood" not in params
    assert "district" not in params


def test_search_caches_the_category_for_the_detail_pass() -> None:
    """The detail page's ``itemOffered.@type`` reads "Apartment" even for land,
    so the searched category is the only trustworthy asset-type signal."""

    async def _inner():
        client = SheypoorClient(settings=TEST_SETTINGS)
        client._session = _FakeSession([_FakeResponse({"data": []})])
        await client.search("iran", "land", 1)
        return client._last_search_category

    assert _run(_inner()) == "land"


def test_get_listing_reads_the_pages_schema_jsonld() -> None:
    html = (
        "<html><script type=\'application/ld+json\'>"
        '{"@type": "Offer", "name": "باغ ۲۰۰ متری"}'
        "</script></html>"
    )

    async def _inner():
        client = SheypoorClient(settings=TEST_SETTINGS)
        client._session = _FakeSession([_FakeResponse(html)])
        detail = await client.get_listing("467417777")
        return client._session.calls[0], detail

    (method, url, _), detail = _run(_inner())
    assert method == "GET"
    assert url.endswith("/v/listing-467417777.html")
    assert detail["@type"] == "Offer"
    assert detail["name"] == "باغ ۲۰۰ متری"
    assert detail["__id"] == "467417777"


def test_get_listing_raises_when_the_page_carries_no_jsonld() -> None:
    async def _inner():
        client = SheypoorClient(settings=TEST_SETTINGS)
        client._session = _FakeSession([_FakeResponse("<html>nothing</html>")])
        await client.get_listing("467417777")

    with pytest.raises(Exception):
        _run(_inner())


def test_get_post_alias_matches_pipeline_interface() -> None:
    """The ingestion pipeline calls ``get_post``; the alias must satisfy it."""
    assert SheypoorClient.get_post is SheypoorClient.get_listing


# --------------------------------------------------------------------- parser


def test_parse_search_reads_items_envelope() -> None:
    payload = {
        "items": [
            {
                "id": 1001,
                "title": "آپارتمان ۸۵ متری",
                "city": "tehran",
                "neighborhood": "سعادت‌آباد",
                "category": "apartment-sell",
                "price": "۳ میلیارد",
            },
            {"listing_id": "1002", "title": "ویلاسازی"},
        ]
    }
    summaries = parse_sheypoor_search(payload)
    assert [s.token for s in summaries] == ["1001", "1002"]
    assert summaries[0].district == "سعادت‌آباد"
    assert summaries[0].price_hint == "۳ میلیارد"


def test_parse_search_handles_nested_data_envelope() -> None:
    payload = {"data": {"listings": [{"id": "A"}, {"id": "B"}]}}
    assert [s.token for s in parse_sheypoor_search(payload)] == ["A", "B"]


def test_parse_search_drops_duplicates_and_id_less_items() -> None:
    payload = {"items": [{"id": "A"}, {"id": "A"}, {"title": "no id"}, {}]}
    assert [s.token for s in parse_sheypoor_search(payload)] == ["A"]


def test_parse_search_empty_envelope_is_empty_list() -> None:
    assert parse_sheypoor_search({}) == []
    assert parse_sheypoor_search({"unexpected": 1}) == []
def test_parse_detail_maps_core_fields() -> None:
    payload = {
        "id": "SP-1",
        "title": "آپارتمان",
        "description": "توضیحات",
        "city": "tehran",
        "neighborhood": "ونک",
        "category": "apartment-sell",
        "price": "۲ میلیارد و ۵۰۰ میلیون",
        "price_per_meter": "۲۹ میلیون",
        "area": "۸۵",
        "rooms": 3,
        "year_built": "۱۳۹۸",
        "floor": "۴",
        "total_floors": 12,
        "elevator": True,
        "parking": True,
        "latitude": "35.7654",
        "longitude": "51.4089",
        "images": ["a.jpg", "b.jpg"],
    }
    detail = parse_sheypoor_detail(payload, "SP-1")
    assert detail.token == "SP-1"
    assert detail.total_price == 2_500_000_000
    assert detail.price_per_meter == 29_000_000
    assert detail.area == 85.0
    assert detail.rooms == 3
    assert detail.year_built == 1398
    assert detail.floor == 4
    assert detail.total_floors == 12
    assert detail.has_elevator is True
    assert detail.has_parking is True
    assert detail.latitude == pytest.approx(35.7654)
    assert detail.longitude == pytest.approx(51.4089)
    assert detail.images == ["a.jpg", "b.jpg"]


def test_parse_detail_rent_splits_deposit_and_rent() -> None:
    payload = {
        "category": "apartment-rent",
        "deposit": "۲۰۰ میلیون",
        "rent": "۱۵ میلیون",
        "area": 100,
    }
    detail = parse_sheypoor_detail(payload, "SP-2")
    assert detail.deal_type == DealType.RENT
    assert detail.deposit == 200_000_000
    assert detail.monthly_rent == 15_000_000
    assert detail.total_price is None


def test_parse_detail_classifies_property_type_from_category() -> None:
    detail = parse_sheypoor_detail({"category": "buy-villa"}, "x")
    assert detail.property_type == PropertyType.VILLA


def test_parse_detail_falls_back_to_nested_spec_block() -> None:
    payload = {"category": "apartment-sell", "spec": {"built_area": "۷۵", "room_count": 2}}
    detail = parse_sheypoor_detail(payload, "SP-3")
    assert detail.area == 75.0
    assert detail.rooms == 2


def test_parse_detail_tolerates_bare_payload() -> None:
    detail = parse_sheypoor_detail({}, "SP-4")
    assert detail.total_price is None
    assert detail.area is None
    assert detail.latitude is None
    assert detail.images == []
    assert detail.property_type == PropertyType.APARTMENT


def test_parse_detail_ignores_blank_coordinates() -> None:
    detail = parse_sheypoor_detail({"latitude": "", "longitude": None}, "SP-5")
    assert detail.latitude is None
    assert detail.longitude is None


def test_parse_detail_carries_phone_through() -> None:
    detail = parse_sheypoor_detail({}, "SP-6", phone="09120000000")
    assert detail.phone == "09120000000"
    """The ingestion pipeline calls ``get_post``; the alias must satisfy it."""
    assert SheypoorClient.get_post is SheypoorClient.get_listing