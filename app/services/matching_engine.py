"""Deterministic spatial matching engine (spec section 4).

Computes a bounded score in ``[0, 100]``:

    Score = (W_spatial * S_geo) + (W_budget * S_price) + (W_specs * S_specs)

with default weights ``W_spatial=0.40``, ``W_budget=0.35``, ``W_specs=0.25``.

The pure helpers below have **no database dependency** so they can be unit
tested and reused by the PostGIS query layer.  Spatial containment / distance is
supplied by PostGIS (``ST_Contains`` / ``ST_Distance``) at the repository level.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
#  Weights & result types
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MatchWeights:
    spatial: float = 0.40
    budget: float = 0.35
    specs: float = 0.25

    def normalized(self) -> "MatchWeights":
        total = self.spatial + self.budget + self.specs
        if total <= 0:
            return MatchWeights()
        return MatchWeights(
            spatial=self.spatial / total,
            budget=self.budget / total,
            specs=self.specs / total,
        )


@dataclass
class MatchBreakdown:
    geo_score: float = 0.0
    price_score: float = 0.0
    specs_score: float = 0.0
    total_score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "geo_score": round(self.geo_score, 2),
            "price_score": round(self.price_score, 2),
            "specs_score": round(self.specs_score, 2),
            "total_score": round(self.total_score, 2),
            "reasons": self.reasons,
        }


# ---------------------------------------------------------------------------
#  Geo score (weight 40%)
# ---------------------------------------------------------------------------
def geo_score(
    *,
    inside_target_area: bool | None = None,
    distance_meters: float | None = None,
    radius_meters: float | None = None,
) -> float:
    """Spatial sub-score.

    * Inside the demand polygon -> ``100``.
    * Radial mode -> inverse-distance decay from ``100`` at the centre to ``0``
      at the search radius.
    """
    if inside_target_area:
        return 100.0
    if distance_meters is not None and radius_meters and radius_meters > 0:
        if distance_meters <= 0:
            return 100.0
        ratio = min(distance_meters / radius_meters, 1.0)
        return round(max(0.0, (1.0 - ratio) * 100.0), 2)
    # No spatial constraint supplied: neutral score.
    return 60.0


# ---------------------------------------------------------------------------
#  Budget score (weight 35%)
# ---------------------------------------------------------------------------
def budget_score(
    price: float | None,
    min_price: float | None,
    max_price: float | None,
    *,
    tolerance: float = 0.10,
) -> float:
    """Budget sub-score.

    * Inside the budget window -> ``100``.
    * Up to ``tolerance`` (default 10%) outside -> linear ``60..99``.
    * Beyond the tolerance band -> ``0``.
    """
    if price is None:
        return 60.0
    lo = min_price if min_price is not None else float("-inf")
    hi = max_price if max_price is not None else float("inf")
    if lo <= price <= hi:
        return 100.0

    if price > hi and hi not in (float("inf"), 0):
        deviation = (price - hi) / hi
    elif price < lo and lo not in (float("-inf"), 0):
        deviation = (lo - price) / lo
    else:
        return 0.0

    if deviation > tolerance:
        return 0.0
    fraction = deviation / tolerance
    return round(99.0 - fraction * (99.0 - 60.0), 2)


# ---------------------------------------------------------------------------
#  Specs score (weight 25%)
# ---------------------------------------------------------------------------
# Sub-weights that sum to 1.0 within the specs bucket.
_SPEC_SUBWEIGHTS = {
    "area": 0.40,
    "rooms": 0.20,
    "age": 0.15,
    "elevator": 0.10,
    "parking": 0.10,
    "floor": 0.05,
}


def _range_score(
    value: float | None,
    lo: float | None,
    hi: float | None,
    tolerance: float = 0.15,
) -> float:
    """Score ``value`` against a desired ``[lo, hi]`` with a ±tolerance band."""
    if value is None or (lo is None and hi is None):
        return 100.0
    lo = lo if lo is not None else float("-inf")
    hi = hi if hi is not None else float("inf")
    if lo <= value <= hi:
        return 100.0
    bound = hi if value > hi else lo
    if bound in (float("inf"), float("-inf"), 0):
        return 100.0
    deviation = abs(value - bound) / abs(bound)
    if deviation > tolerance:
        return 0.0
    return round(60.0 + (1 - deviation / tolerance) * 40.0, 2)


def specs_score(
    *,
    area: float | None = None,
    min_area: float | None = None,
    max_area: float | None = None,
    rooms: int | None = None,
    min_rooms: int | None = None,
    max_rooms: int | None = None,
    building_age: int | None = None,
    max_building_age: int | None = None,
    floor: int | None = None,
    preferred_floor: int | None = None,
    has_elevator: bool | None = None,
    requires_elevator: bool = False,
    has_parking: bool | None = None,
    requires_parking: bool = False,
) -> float:
    """Facility/attribute sub-score composed of weighted components."""
    components: dict[str, float] = {}

    components["area"] = _range_score(area, min_area, max_area)
    components["rooms"] = _range_score(rooms, min_rooms, max_rooms, tolerance=0.34)

    if building_age is None or max_building_age is None:
        components["age"] = 100.0
    elif building_age <= max_building_age:
        components["age"] = 100.0
    else:
        over = building_age - max_building_age
        components["age"] = round(max(0.0, 100.0 - over * 5.0), 2)

    components["elevator"] = (
        100.0 if has_elevator else (0.0 if requires_elevator else 80.0)
        if has_elevator is not None
        else 100.0
    )
    components["parking"] = (
        100.0 if has_parking else (0.0 if requires_parking else 80.0)
        if has_parking is not None
        else 100.0
    )

    if floor is None or preferred_floor is None:
        components["floor"] = 100.0
    else:
        diff = abs(floor - preferred_floor)
        components["floor"] = round(max(0.0, 100.0 - diff * 20.0), 2)

    total = sum(components[name] * _SPEC_SUBWEIGHTS[name] for name in _SPEC_SUBWEIGHTS)
    return round(total, 2)


# ---------------------------------------------------------------------------
#  Combined score
# ---------------------------------------------------------------------------
def compute_match_score(
    *,
    inside_target_area: bool | None = None,
    distance_meters: float | None = None,
    radius_meters: float | None = None,
    price: float | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    weights: MatchWeights | None = None,
    **specs_kwargs,
) -> MatchBreakdown:
    """Compute the full weighted match score and a human-readable breakdown."""
    w = (weights or MatchWeights()).normalized()
    s_geo = geo_score(
        inside_target_area=inside_target_area,
        distance_meters=distance_meters,
        radius_meters=radius_meters,
    )
    s_price = budget_score(price, min_price, max_price)
    s_specs = specs_score(**specs_kwargs)

    total = s_geo * w.spatial + s_price * w.budget + s_specs * w.specs
    reasons: list[str] = []
    if s_geo >= 80:
        reasons.append("موقعیت مکانی منطبق")
    if s_price >= 80:
        reasons.append("بودجه مناسب")
    if s_specs >= 80:
        reasons.append("مشخصات فنی مطابق")

    return MatchBreakdown(
        geo_score=s_geo,
        price_score=s_price,
        specs_score=s_specs,
        total_score=round(min(100.0, max(0.0, total)), 2),
        reasons=reasons,
    )
