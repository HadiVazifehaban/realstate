"""Offline tests for the Delta source: flight-data extraction and normalisation.

These deliberately do **not** hit delta.ir. The extractor is the fragile part --
it depends on how Next.js serialises the RSC flight payload -- so it is pinned
against a captured sample rather than the live site, which would make the suite
fail whenever Delta ships a redesign.
"""

from __future__ import annotations

import json

import pytest

from app.models.enums import DealType, PropertySource, PropertyType
from app.services.scraper import registry
from app.services.scraper.delta_client import (
    DeltaClient,
    extract_detail_jsonld,
    extract_listing_ids,
    normalise_listing_id,
)
from app.services.scraper.delta_parser import (
    parse_delta_detail,
    parse_delta_search,
)
from app.services.scraper.delta_taxonomy import listing_id_from_url

# A real Delta JSON-LD body, trimmed. `priceCurrency` really does say "IRR"
# while the figure is toman -- that discrepancy is the whole reason the parser
# documents it.
_LD = {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "139 متر / فول / اقدسیه / ",
    "title": "139 متر / فول / اقدسیه / ",
    "url": "https://delta.ir/detail/101257",
    "image": [f"https://cdn.delta.ir/photo-{i}.webp?X-Amz-Expires=86400" for i in range(3)],
    "offeredBy": {"@type": "RealAgent", "name": "آراز", "url": "https://delta.ir/realator/4322"},
    "realEstateAgency": {
        "@type": "RealEstateAgency",
        "name": "گروه مشاورین املاک آراز",
        "url": "https://delta.ir/agency/700",
    },
    "offers": {
        "price": "53,000,000,000",
        "priceCurrency": "IRR",
        "additionalProperty": {
            "@type": "PropertyValue",
            "name": "قیمت متری",
            "value": "381,295,000",
        },
    },
    "item": {
        "name": "139 متر / فول / اقدسیه / ",
        "floorSize": {"@type": "QuantitativeValue", "unitCode": "MTK"},
        "numberOfRooms": "3",
        "floorLevel": "2",
        "amenityFeature": [
            {"@type": "LocationFeatureSpecification", "name": "مساحت ملک", "value": "139"},
            {"@type": "LocationFeatureSpecification", "name": "پارکینگ", "value": "true"},
            {"@type": "LocationFeatureSpecification", "name": "آسانسور", "value": "true"},
            {"@type": "LocationFeatureSpecification", "name": "انباری", "value": "false"},
            {"@type": "LocationFeatureSpecification", "name": "عمر تقریبی بنا", "value": "‫19 ساله‬"},
            {"@type": "LocationFeatureSpecification", "name": "طبقه", "value": "2"},
            {"@type": "LocationFeatureSpecification", "name": "تعداد اتاق", "value": "3"},
        ],
    },
}


def _flight_page(rows: dict[str, str], *, preferred: str = "28:") -> str:
    """Wrap row payloads the way Next.js does: one push per chunk."""
    chunks = ["<html><body><script>"]
    for row_id, payload in rows.items():
        chunks.append(f"self.__next_f.push([1,{json.dumps(row_id + payload)}])")
    chunks.append("</script></body></html>")
    return "".join(chunks)


def _escaped_ld(ld: dict) -> str:
    """The JSON-LD as it appears inside a flight row: a quoted, escaped string."""
    return json.dumps(json.dumps(ld, ensure_ascii=False))


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------
def test_extracts_product_from_the_preferred_flight_row() -> None:
    html = _flight_page({"27:": "junk", "28:": _escaped_ld(_LD)})
    got = extract_detail_jsonld(html)
    assert got["@type"] == "Product"
    assert got["offers"]["price"] == "53,000,000,000"
    assert len(got["image"]) == 3


def test_falls_back_to_another_row_when_the_preferred_id_moves() -> None:
    """Delta renumbers flight rows between deploys; that must not lose listings."""
    html = _flight_page({"99:": "junk", "a1b2c3d4e5:": _escaped_ld(_LD)})
    assert extract_detail_jsonld(html, preferred_row="28:")["@type"] == "Product"


def test_reassembles_a_row_split_across_two_pushes() -> None:
    """A streaming boundary can cut one flight row in half."""
    escaped = _escaped_ld(_LD)
    head, tail = escaped[:40], escaped[40:]
    html = (
        "<script>self.__next_f.push([1,"
        + json.dumps("28:" + head)
        + "])</script><script>self.__next_f.push([1,"
        + json.dumps(tail)
        + "])</script>"
    )
    assert extract_detail_jsonld(html)["@type"] == "Product"


def test_returns_empty_dict_when_the_page_carries_no_listing() -> None:
    assert extract_detail_jsonld("<html><body>nothing here</body></html>") == {}


def test_ignores_a_flight_row_that_is_not_a_product() -> None:
    html = _flight_page({"28:": json.dumps({"@type": "WebPage", "name": "x"})})
    assert extract_detail_jsonld(html) == {}


def test_listing_ids_are_collected_and_deduplicated() -> None:
    html = '<a href="/detail/105785">a</a><a href="/detail/105977">b</a><a href="/detail/105785">c</a>'
    assert extract_listing_ids(html) == ["105785", "105977"]


# --------------------------------------------------------------------------
# URL normalisation -- the five supported detail shapes
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://delta.ir/detail/101257", "101257"),
        ("https://delta.ir/tehran/detail/101257", "101257"),
        ("https://delta.ir/tehran/buy/apartment/detail/101257", "101257"),
        ("https://delta.ir/listing/101257", "101257"),
        ("https://delta.ir/101257", "101257"),
        ("https://delta.ir/price-trends", None),
        ("https://delta.ir/search-map", None),
    ],
)
def test_listing_id_from_every_supported_url_shape(url: str, expected: str | None) -> None:
    assert listing_id_from_url(url) == expected


def test_normalise_listing_id_accepts_bare_ids_and_urls() -> None:
    assert normalise_listing_id("101257") == "101257"
    assert normalise_listing_id("https://delta.ir/detail/101257") == "101257"


# --------------------------------------------------------------------------
# Normalisation onto the unified schema
# --------------------------------------------------------------------------
def test_price_is_read_as_toman_not_rial() -> None:
    d = parse_delta_detail(_LD, "101257")
    assert d.total_price == 53_000_000_000
    assert d.price_per_meter == 381_295_000
    # 53bn / 139m2 is the listing's own price-per-metre. If the figure were
    # rial this identity would not hold.
    assert abs(d.total_price / d.area - d.price_per_meter) / d.price_per_meter < 0.01


def test_specs_and_amenities_map_onto_the_unified_fields() -> None:
    d = parse_delta_detail(_LD, "101257")
    assert d.area == 139.0
    assert d.rooms == 3
    assert d.floor == 2
    assert d.has_parking is True
    assert d.has_elevator is True
    assert d.has_storage is False
    # 1404 - 19 years old.
    assert d.year_built == 1385


def test_agent_and_agency_are_captured_for_the_advisor_card() -> None:
    d = parse_delta_detail(_LD, "101257")
    assert d.agent_name == "آراز"
    assert d.agent_slug == "4322"
    assert d.business_type == "AGENCY"


def test_a_listing_with_no_agency_is_marked_personal() -> None:
    payload = {**_LD}
    payload.pop("realEstateAgency")
    assert parse_delta_detail(payload, "101257").business_type == "PERSONAL"


def test_type_and_deal_fall_back_to_the_search_context() -> None:
    """Delta's canonical /detail/{id} URL carries no type segment at all."""
    d = parse_delta_detail(_LD, "101257")
    assert d.property_type is None and d.deal_type is None

    payload = {**_LD, "__context": {"property_type": "apartment", "deal": "rent"}}
    d = parse_delta_detail(payload, "101257")
    assert d.property_type is PropertyType.APARTMENT
    assert d.deal_type is DealType.RENT


def test_type_and_deal_are_read_from_a_typed_detail_url() -> None:
    payload = {**_LD, "url": "https://delta.ir/tehran/buy/villa/detail/101257"}
    d = parse_delta_detail(payload, "101257")
    assert d.property_type is PropertyType.VILLA
    assert d.deal_type is DealType.SALE


def test_area_falls_back_to_the_leading_number_of_the_item_name() -> None:
    payload = {**_LD}
    payload["item"] = {**_LD["item"]}
    payload["item"]["amenityFeature"] = [
        a for a in payload["item"]["amenityFeature"] if a["name"] != "مساحت ملک"
    ]
    assert parse_delta_detail(payload, "101257").area == 139.0


def test_images_keep_the_presigned_urls_for_the_ingestor_to_download() -> None:
    d = parse_delta_detail(_LD, "101257")
    assert len(d.images) == 3
    assert all("X-Amz-Expires" in url for url in d.images)


def test_search_summary_carries_only_the_id_by_design() -> None:
    """Delta list pages hold links, not structured data."""
    summaries = parse_delta_search({"listing_ids": ["105785", "105977"], "url": "u"})
    assert [s.token for s in summaries] == ["105785", "105977"]
    assert summaries[0].title == ""
    assert summaries[0].raw["detail_url"].endswith("/detail/105785")


def test_empty_search_page_yields_no_summaries() -> None:
    assert parse_delta_search({"listing_ids": []}) == []


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------
def test_delta_is_routable_and_namespaced() -> None:
    spec = registry.get_source("delta")
    assert spec.client_factory is DeltaClient
    assert spec.property_source is PropertySource.DELTA
    assert spec.external_id_prefix == "delta:"
    assert spec.supports_phone_extraction is False


def test_a_trade_listing_ingests_as_a_sale_rather_than_being_dropped() -> None:
    payload = {**_LD, "__context": {"property_type": "land", "deal": "trade"}}
    d = parse_delta_detail(payload, "101257")
    assert d.property_type is PropertyType.LAND
    assert d.deal_type is DealType.SALE