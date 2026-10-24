"""MLS privacy masking (spec section 3 Phase 3).

Converts a private office listing into an **anonymous, shareable** record for
the co-broker network:

* owner name / phone are removed entirely,
* the exact location is fuzzed to a ~300 m radius (no door number / pelak),
* only technical + financial attributes survive.

Implemented as pure functions so they are easy to unit test.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

MLS_FUZZ_RADIUS_METERS = 300
_EARTH_RADIUS_M = 6_371_000.0

# Keys that must never appear in a masked payload.
_FORBIDDEN_KEYS = {
    "owner_name",
    "owner_phone",
    "owner_name_enc",
    "owner_phone_enc",
    "owner_phone_alt_enc",
    "exact_address",
    "exact_address_enc",
    "pelak",
    "pelak_unit_enc",
    "national_id_enc",
    "source_ref",
    "created_by_id",
}


@dataclass
class MaskedListing:
    """The anonymised listing payload pushed to the MLS hub."""

    payload: dict[str, Any]
    fuzzed_lat: float | None = None
    fuzzed_lng: float | None = None
    exact_point_removed: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "payload": self.payload,
            "fuzzed_lat": self.fuzzed_lat,
            "fuzzed_lng": self.fuzzed_lng,
            "exact_point_removed": self.exact_point_removed,
        }


def fuzz_location(
    lat: float,
    lng: float,
    *,
    radius_meters: float = MLS_FUZZ_RADIUS_METERS,
    rng: random.Random | None = None,
    distribution: str = "gaussian",
) -> tuple[float, float]:
    """Offset a coordinate by random noise within ``radius_meters``.

    ``distribution``:
      * ``"gaussian"`` -- half-normal radial distance + uniform bearing (default
        per the v2.0 spec: "نویز گاوسی تا شعاع ۳۰۰ متر").
      * ``"uniform"``  -- sqrt-uniform disc sampling.

    Uses the equirectangular approximation, accurate enough at the ~300 m scale
    required for MLS privacy.
    """
    rng = rng or random.Random()
    if distribution == "uniform":
        distance = radius_meters * math.sqrt(rng.random())
    else:
        # Half-normal magnitude, clamped to the radius -> Gaussian-ish jitter.
        distance = abs(rng.gauss(0.0, radius_meters / 2.0))
        distance = min(distance, radius_meters)
    bearing = rng.uniform(0, 2 * math.pi)

    d_lat = (distance * math.cos(bearing)) / _EARTH_RADIUS_M
    d_lng = (distance * math.sin(bearing)) / (
        _EARTH_RADIUS_M * max(math.cos(math.radians(lat)), 1e-6)
    )
    return round(lat + math.degrees(d_lat), 6), round(lng + math.degrees(d_lng), 6)


def _strip_forbidden(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k not in _FORBIDDEN_KEYS}


def mask_listing(
    listing: dict[str, Any],
    *,
    lat: float | None = None,
    lng: float | None = None,
    fuzz_radius_meters: float = MLS_FUZZ_RADIUS_METERS,
    rng: random.Random | None = None,
) -> MaskedListing:
    """Return an anonymised copy of ``listing`` safe for MLS sharing."""
    safe = _strip_forbidden(dict(listing))

    fuzzed_lat: float | None = None
    fuzzed_lng: float | None = None
    if lat is not None and lng is not None:
        fuzzed_lat, fuzzed_lng = fuzz_location(
            lat, lng, radius_meters=fuzz_radius_meters, rng=rng
        )
        # Provide an approximate circle instead of the exact point.
        safe["approx_lat"] = fuzzed_lat
        safe["approx_lng"] = fuzzed_lng
        safe["fuzz_radius_meters"] = fuzz_radius_meters

    # Never leak the precise geometry.
    safe.pop("location", None)
    safe.pop("exact_address", None)

    return MaskedListing(
        payload=safe,
        fuzzed_lat=fuzzed_lat,
        fuzzed_lng=fuzzed_lng,
        exact_point_removed=True,
    )
