"""Tests for the deterministic weighted matching engine (spec section 4)."""

from __future__ import annotations

from app.services.matching_engine import (
    MatchWeights,
    budget_score,
    compute_match_score,
    geo_score,
    specs_score,
)


def test_geo_inside_area_is_full() -> None:
    assert geo_score(inside_target_area=True) == 100.0


def test_geo_radial_decay() -> None:
    assert geo_score(distance_meters=0, radius_meters=1000) == 100.0
    assert geo_score(distance_meters=500, radius_meters=1000) == 50.0
    assert geo_score(distance_meters=1000, radius_meters=1000) == 0.0
    # Beyond the radius clamps at zero.
    assert geo_score(distance_meters=5000, radius_meters=1000) == 0.0


def test_geo_neutral_when_unconstrained() -> None:
    assert geo_score() == 60.0


def test_budget_inside_window() -> None:
    assert budget_score(9_000, 8_000, 10_000) == 100.0


def test_budget_partial_tolerance() -> None:
    # 5% above the ceiling -> inside the 10% tolerance band.
    score = budget_score(10_500, None, 10_000)
    assert 60.0 < score < 100.0


def test_budget_beyond_tolerance_is_zero() -> None:
    assert budget_score(12_000, None, 10_000) == 0.0
    assert budget_score(7_000, 10_000, None) == 0.0


def test_specs_all_matching_is_full() -> None:
    score = specs_score(
        area=100,
        min_area=90,
        max_area=110,
        rooms=2,
        min_rooms=2,
        max_rooms=3,
        building_age=5,
        max_building_age=10,
        floor=3,
        preferred_floor=3,
        has_elevator=True,
        requires_elevator=True,
        has_parking=True,
        requires_parking=True,
    )
    assert score == 100.0


def test_specs_missing_required_parking_penalised() -> None:
    score = specs_score(
        area=100, min_area=90, max_area=110, has_parking=False, requires_parking=True
    )
    # The parking component carries a 0.10 sub-weight -> exactly 10 points lost.
    assert score == 90.0
    assert score < specs_score(area=100, min_area=90, max_area=110, has_parking=True)


def test_combined_perfect_match() -> None:
    result = compute_match_score(
        inside_target_area=True,
        price=9_000,
        min_price=8_000,
        max_price=10_000,
        area=100,
        min_area=90,
        max_area=110,
        rooms=2,
        min_rooms=2,
        max_rooms=3,
        has_elevator=True,
        requires_elevator=True,
        has_parking=True,
        requires_parking=True,
    )
    assert result.total_score == 100.0
    assert len(result.reasons) == 3


def test_combined_poor_match_is_low() -> None:
    result = compute_match_score(
        inside_target_area=False,
        distance_meters=5000,
        radius_meters=1000,
        price=50_000,
        min_price=8_000,
        max_price=10_000,
        area=500,
        min_area=90,
        max_area=110,
        has_parking=False,
        requires_parking=True,
    )
    assert result.total_score < 40.0


def test_score_is_bounded_0_100() -> None:
    result = compute_match_score(
        inside_target_area=True,
        price=9_000,
        min_price=8_000,
        max_price=10_000,
    )
    assert 0.0 <= result.total_score <= 100.0


def test_custom_weights_are_normalised() -> None:
    weights = MatchWeights(spatial=1, budget=1, specs=1).normalized()
    assert abs(weights.spatial - 1 / 3) < 1e-9


def test_breakdown_as_dict() -> None:
    result = compute_match_score(inside_target_area=True, price=9_000, min_price=8_000, max_price=10_000)
    data = result.as_dict()
    assert set(data) == {"geo_score", "price_score", "specs_score", "total_score", "reasons"}
