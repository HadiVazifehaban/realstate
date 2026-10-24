"""Tests for MLS privacy masking (owner-free, location-fuzzed payloads)."""

from __future__ import annotations

import math
import random

from app.services.mls_masking import (
    MLS_FUZZ_RADIUS_METERS,
    _EARTH_RADIUS_M,
    fuzz_location,
    mask_listing,
)


def test_mask_removes_owner_fields() -> None:
    listing = {
        "title": "آپارتمان ۱۰۰ متری",
        "area": 100,
        "owner_name": "حسین رضایی",
        "owner_phone": "09120000000",
        "exact_address": "خیابان ولیعصر پلاک ۱۰",
        "pelak_unit_enc": "token",
        "location": "POINT(...)",
        "total_price": 9_000_000_000,
    }
    masked = mask_listing(listing, lat=35.7, lng=51.4)
    payload = masked.payload

    for forbidden in ("owner_name", "owner_phone", "exact_address", "pelak_unit_enc", "location"):
        assert forbidden not in payload
    # Technical/financial data survives.
    assert payload["area"] == 100
    assert payload["total_price"] == 9_000_000_000
    assert payload["approx_lat"] is not None
    assert payload["fuzz_radius_meters"] == MLS_FUZZ_RADIUS_METERS


def test_mask_without_coordinates_has_no_fuzz() -> None:
    masked = mask_listing({"title": "x", "owner_phone": "1"}, lat=None, lng=None)
    assert masked.fuzzed_lat is None
    assert "approx_lat" not in masked.payload


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def test_fuzz_location_stays_within_radius() -> None:
    rng = random.Random(42)
    lat, lng = 35.7, 51.4
    for _ in range(200):
        f_lat, f_lng = fuzz_location(lat, lng, radius_meters=300, rng=rng)
        distance = _haversine(lat, lng, f_lat, f_lng)
        # Allow a small margin for the equirectangular approximation.
        assert distance <= 300 * 1.05


def test_fuzz_location_changes_point() -> None:
    rng = random.Random(1)
    f_lat, f_lng = fuzz_location(35.7, 51.4, rng=rng)
    assert (f_lat, f_lng) != (35.7, 51.4)


def test_masked_listing_as_dict() -> None:
    masked = mask_listing({"title": "t"}, lat=35.0, lng=51.0)
    data = masked.as_dict()
    assert set(data) == {"payload", "fuzzed_lat", "fuzzed_lng", "exact_point_removed"}
    assert data["exact_point_removed"] is True
