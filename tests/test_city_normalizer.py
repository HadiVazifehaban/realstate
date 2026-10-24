"""City normaliser: non-city values must never occupy ``Property.city``."""

from app.services.city_normalizer import is_known_city, normalize_city_neighborhood


def test_known_persian_cities_pass() -> None:
    assert is_known_city("تهران") is True
    assert is_known_city("تبریز") is True
    assert is_known_city("پردیس") is True


def test_latin_slugs_pass() -> None:
    assert is_known_city("tehran") is True
    assert is_known_city("Tehran") is True


def test_neighbourhoods_and_phases_rejected() -> None:
    for junk in ["پونک", "فاز ۱", "فاز 11", "خیابان بابل", "بلوار منفرد", "مرکز شهر", "16 متری", "شهرک مریم", ""]:
        assert is_known_city(junk) is False, junk


def test_non_city_demoted_to_neighborhood() -> None:
    city, area = normalize_city_neighborhood("پونک", "")
    assert city == ""
    assert area == "پونک"


def test_non_city_appended_when_area_occupied() -> None:
    city, area = normalize_city_neighborhood("فاز 1", "پردیس")
    assert city == ""
    assert "فاز 1" in area
    assert "پردیس" in area


def test_real_city_untouched() -> None:
    city, area = normalize_city_neighborhood("تهران", "پونک")
    assert city == "تهران"
    assert area == "پونک"


def test_slug_city_untouched() -> None:
    city, area = normalize_city_neighborhood("tehran", "saadat-abad")
    assert city == "tehran"
    assert area == "saadat-abad"
