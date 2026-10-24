"""Tests for Sheypoor's real-estate category registry and URL builders.

The ``c=`` ids are the part of Sheypoor the node cannot guess: an unknown one
returns 200 with an unrelated listing set rather than an error, so a wrong id
crawls the wrong inventory silently. These tests pin the ids and the two lossy
mappings that are deliberate rather than accidental.
"""

from __future__ import annotations

import pytest

from app.models.enums import DealType, PropertyType
from app.services.scraper.sheypoor_taxonomy import (
    ROOT_CATEGORY_ID,
    SHEYPOOR_CATEGORIES,
    build_detail_url,
    build_list_url,
    map_category_to_types,
    resolve_category_id,
    resolve_slug,
)


def test_every_menu_entry_has_a_distinct_id() -> None:
    ids = [c.category_id for c in SHEYPOOR_CATEGORIES if c.category_id is not None]
    assert len(ids) == len(set(ids))
    assert ROOT_CATEGORY_ID == 43603


@pytest.mark.parametrize(
    "slug,cat_id",
    [
        ("houses-apartments-for-sale", 43604),
        ("commercial-properties-for-sale", 43605),
        ("house-apartment-for-rent", 43606),
        ("commercial-properties-for-rent", 43607),
        ("real-estate-short-term-rental", 44585),
        ("villa-for-sale", 44586),
        ("land", 44099),
        ("real-estate-services", 45001),
        ("other-real-estate", 44115),
    ],
)
def test_known_slugs_resolve_to_their_category_id(slug: str, cat_id: int) -> None:
    category = resolve_slug(slug)
    assert category is not None
    assert category.category_id == cat_id
    # And the reverse lookup, which is what a `?c=` query actually carries.
    assert resolve_category_id(cat_id) is category
    assert resolve_category_id(str(cat_id)) is category


def test_slug_lookup_tolerates_case_and_whitespace() -> None:
    assert resolve_slug("  LAND ") is resolve_slug("land")


def test_unknown_slug_resolves_to_nothing() -> None:
    assert resolve_slug("atlantis") is None
    assert resolve_category_id("99999") is None
    assert resolve_category_id(None) is None
    assert map_category_to_types("atlantis") == (None, None)


@pytest.mark.parametrize(
    "slug,prop,deal",
    [
        ("houses-apartments-for-sale", PropertyType.APARTMENT, DealType.SALE),
        ("house-apartment-for-rent", PropertyType.APARTMENT, DealType.RENT),
        ("villa-for-sale", PropertyType.VILLA, DealType.SALE),
        ("land", PropertyType.LAND, DealType.SALE),
    ],
)
def test_direct_categories_map_exactly(
    slug: str, prop: PropertyType, deal: DealType
) -> None:
    assert map_category_to_types(slug) == (prop, deal)


def test_short_let_is_ingested_as_rent() -> None:
    """No short-let member exists in the unified schema; this is deliberate."""
    assert map_category_to_types("real-estate-short-term-rental")[1] is DealType.RENT


def test_presale_is_ingested_as_a_sale() -> None:
    """The enum has no PRE_SALE; its third member is FULL_MORTGAGE."""
    assert map_category_to_types("real-estate-services") == (
        PropertyType.APARTMENT,
        DealType.SALE,
    )


@pytest.mark.parametrize(
    "slug,deal",
    [
        ("commercial-properties-for-sale", DealType.SALE),
        ("commercial-properties-for-rent", DealType.RENT),
    ],
)
def test_commercial_slugs_omit_the_property_type(slug: str, deal: DealType) -> None:
    """Shop/office/warehouse is only in the listing body, so it is left unset."""
    prop, mapped_deal = map_category_to_types(slug)
    assert prop is None
    assert mapped_deal is deal


def test_list_url_carries_slug_and_category_id() -> None:
    url = build_list_url("iran", "land")
    assert url == "https://www.sheypoor.com/s/iran/land?c=44099"
    assert build_list_url("fars", "land", page=3).endswith("&p=3")


def test_list_url_rejects_an_unknown_category() -> None:
    """Better a loud job failure than a 200 full of the wrong listings."""
    with pytest.raises(ValueError):
        build_list_url("iran", "atlantis")


def test_detail_url_carries_the_numeric_id_last() -> None:
    url = build_detail_url("467417777")
    assert url == "https://www.sheypoor.com/v/listing-467417777.html"
    assert url.rstrip("/").split("-")[-1].removesuffix(".html") == "467417777"