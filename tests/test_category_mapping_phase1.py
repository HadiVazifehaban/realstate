"""Offline regression checks for verified category mapping only."""

import pytest

from app.services.scraper.category_mapping import (
    UnsupportedCategoryError,
    resolve_categories,
)


@pytest.mark.parametrize(
    ("source", "category", "expected"),
    [
        ("delta", "apartment-sell", ("apartment-sell",)),
        ("delta", "apartment-rent", ("apartment-rent",)),
        ("sheypoor", "apartment-sell", ("houses-apartments-for-sale",)),
        ("sheypoor", "house-villa-sell", ("houses-apartments-for-sale",)),
        ("sheypoor", "apartment-rent", ("house-apartment-for-rent",)),
        ("sheypoor", "house-villa-rent", ("house-apartment-for-rent",)),
    ],
)
def test_verified_category_mapping(source, category, expected):
    result = resolve_categories(source, category)
    assert result.categories == expected
    assert result.status == "SUPPORTED"


@pytest.mark.parametrize(
    ("source", "category"),
    [
        ("delta", "house-villa-sell"),
        ("delta", "house-villa-rent"),
        ("sheypoor", "not-a-category"),
        ("divar", "apartment-sell"),
        ("unknown", "apartment-sell"),
    ],
)
def test_unverified_category_fails_closed(source, category):
    with pytest.raises(UnsupportedCategoryError) as error:
        resolve_categories(source, category)
    assert error.value.status == "UNSUPPORTED"