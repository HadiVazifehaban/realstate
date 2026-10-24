"""Automated valuation engine (Phase 3b) -- deterministic, offline-capable.

Decides whether a listing sits below, at or above its local market:

1. build a cohort of comparables (same city / neighbourhood / type / deal, same
   bedroom bucket, rolling window, radius limit);
2. derive price-per-metre for each one, weighting nearer matches higher;
3. take a *weighted median* (a mean would be dragged around by one luxury tower)
   and trim MAD outliers;
4. compare the subject against that median and label it.

No network calls, so a ``LOCAL`` office node keeps valuing offline and every
verdict stays reproducible for a later audit.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import get_logger
from app.models import Property
from app.models.base import utcnow
from app.models.enums import DealType, PropertyStatus, ValuationStatus
from app.services.events import NEW_PROPERTY_INGESTED, event_bus

logger = get_logger("app.valuation")

# -- Tunables: the commercial build is deterministic, so they live in code. --
WINDOW_DAYS = 90
MIN_SAMPLES = 8
BARGAIN_THRESHOLD_PCT = -15.0
OVERPRICED_THRESHOLD_PCT = 10.0
NEAR_RADIUS_M = 800
MID_RADIUS_M = 2000
MAX_RADIUS_M = 5000
# Plausibility band for a Toman price-per-metre; anything outside is junk data.
MIN_PPSQM = 200_000
MAX_PPSQM = 200_000_000


@dataclass
class Comparable:
    """A cohort member reduced to what the estimator actually needs."""

    property_id: str
    price_per_meter: float
    distance_m: float
    weight: float = 1.0


@dataclass
class ValuationResult:
    """Explainable verdict; ``explain`` is what a supervisor may have to defend."""

    status: ValuationStatus
    deviation_pct: float | None = None
    median_price_per_meter: int | None = None
    sample_count: int = 0
    explain: dict = field(default_factory=dict)

    @property
    def is_bargain(self) -> bool:
        return self.status is ValuationStatus.BARGAIN


def radius_weight(distance_m: float) -> float:
    if distance_m <= NEAR_RADIUS_M:
        return 1.0
    if distance_m <= MID_RADIUS_M:
        return 0.6
    return 0.3


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def _weighted_median(samples: list[Comparable], quantile: float = 0.5) -> float:
    ordered = sorted(samples, key=lambda s: s.price_per_meter)
    total = sum(s.weight for s in ordered)
    if total <= 0:
        return 0.0
    cumulative = 0.0
    target = total * quantile
    for sample in ordered:
        cumulative += sample.weight
        if cumulative >= target:
            return sample.price_per_meter
    return ordered[-1].price_per_meter


def price_per_meter(total_price: int | None, area: float | None) -> float | None:
    """Asked price per square metre, or ``None`` when it cannot be computed."""
    if not total_price or not area or area <= 0:
        return None
    return total_price / area


def effective_ppsqm(property_: Property) -> float | None:
    """Rentals are compared on annualised rent or deposit, sales on the asking price."""
    if property_.deal_type == DealType.RENT:
        if property_.monthly_rent is None:
            return None
        annual = property_.monthly_rent * 12
        return price_per_meter(annual, property_.area)
    elif property_.deal_type == DealType.FULL_MORTGAGE:
        if property_.deposit_amount is None:
            return None
        return price_per_meter(property_.deposit_amount, property_.area)
    else:  # SALE
        return price_per_meter(property_.total_price, property_.area)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    radius = 6_371_000.0
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def evaluate(subject: Property, comparables: list[Comparable]) -> ValuationResult:
    """Pure estimator: subject plus cohort in, explainable verdict out."""
    observed = effective_ppsqm(subject)
    if observed is None:
        return ValuationResult(ValuationStatus.UNKNOWN, explain={"reason": "missing_price_or_area"})
    if not comparables:
        return ValuationResult(ValuationStatus.UNKNOWN, explain={"reason": "empty_cohort"})

    plausible: list[Comparable] = []
    dropped = 0
    for sample in comparables:
        if not (MIN_PPSQM <= sample.price_per_meter <= MAX_PPSQM):
            dropped += 1
            continue
        sample.weight = sample.weight or radius_weight(sample.distance_m)
        plausible.append(sample)

    if not plausible:
        return ValuationResult(
            ValuationStatus.UNKNOWN, explain={"reason": "all_outliers", "dropped": dropped}
        )

    median = _weighted_median(plausible)
    mad = _median([abs(s.price_per_meter - median) for s in plausible])
    # A zero MAD means a perfectly uniform cohort -- nothing to trim.
    trimmed = plausible if mad == 0 else [
        s for s in plausible if abs(s.price_per_meter - median) <= 3 * 1.4826 * mad
    ]

    explain: dict = {
        "cohort_size": len(comparables),
        "dropped_outliers": dropped,
        "n_valid": len(trimmed),
        "observed_ppsqm": round(observed, 2),
        "window_days": WINDOW_DAYS,
        "min_samples": MIN_SAMPLES,
        "thresholds": {
            "bargain": BARGAIN_THRESHOLD_PCT,
            "overpriced": OVERPRICED_THRESHOLD_PCT,
        },
    }

    if len(trimmed) < MIN_SAMPLES:
        return ValuationResult(
            ValuationStatus.UNKNOWN,
            sample_count=len(trimmed),
            explain={**explain, "reason": "insufficient_samples"},
        )

    benchmark = _weighted_median(trimmed)
    deviation_pct = 100.0 * (observed - benchmark) / benchmark
    return ValuationResult(
        status=label_for(deviation_pct),
        deviation_pct=round(deviation_pct, 2),
        median_price_per_meter=int(benchmark),
        sample_count=len(trimmed),
        explain={**explain, "median_ppsqm": round(benchmark, 2)},
    )


def postgis_distance_m(a: Property, b: Property) -> float:
    """Great-circle distance in metres between two ``location`` points."""
    from geoalchemy2.shape import to_shape

    try:
        pa, pb = to_shape(a.location), to_shape(b.location)
    except Exception:  # pragma: no cover - defensive for non-PostGIS geometries
        return float("inf")
    return haversine_m(pa.y, pa.x, pb.y, pb.x)


async def build_cohort(
    session: AsyncSession,
    subject: Property,
    *,
    window_days: int = WINDOW_DAYS,
    radius_m: int = MAX_RADIUS_M,
) -> list[Comparable]:
    """Comparable set for ``subject``, excluding the subject itself.

    Distance is computed in Python from the stored points so the same code runs
    on SQLite (unit tests) and PostGIS; production deployments should additionally
    pre-filter with ``ST_DWithin`` on the GiST index via ``find_nearby_properties``.
    """
    if not subject.city or not subject.neighborhood:
        return []

    query = select(Property).where(
        Property.id != subject.id,
        Property.city == subject.city,
        Property.neighborhood == subject.neighborhood,
        Property.deal_type == subject.deal_type,
        Property.property_type == subject.property_type,
        Property.status == PropertyStatus.ACTIVE,
    )
    if window_days > 0:
        query = query.where(Property.created_at >= utcnow() - timedelta(days=window_days))

    rows = (await session.exec(query)).all()
    cohort: list[Comparable] = []
    for row in rows:
        ppsqm = effective_ppsqm(row)
        if ppsqm is None:
            continue
        distance = 0.0
        if subject.location is not None and row.location is not None:
            distance = postgis_distance_m(subject, row)
            if distance > radius_m:
                continue
        same_bucket = bedroom_bucket(row.rooms) == bedroom_bucket(subject.rooms)
        cohort.append(Comparable(
            property_id=str(row.id),
            price_per_meter=ppsqm,
            distance_m=distance,
            # Room-count parity down-weights a comparable, never removes it.
            weight=1.0 if same_bucket else 0.5,
        ))
    return cohort


async def value_property(
    session: AsyncSession, property_: Property, *, persist: bool = True
) -> ValuationResult:
    """Run the engine for one property and (by default) store the verdict."""
    result = evaluate(property_, await build_cohort(session, property_))
    if persist:
        property_.valuation_status = result.status
        property_.valuation_deviation_pct = result.deviation_pct
        property_.valuation_median_price_per_meter = result.median_price_per_meter
        property_.valuation_sample_count = result.sample_count
        property_.valuation_updated_at = utcnow()
        session.add(property_)
        await session.commit()
    logger.info(
        "valued property=%s status=%s deviation=%s samples=%s",
        property_.id, result.status.value, result.deviation_pct, result.sample_count,
    )
    return result


async def value_neighbourhood(
    session: AsyncSession,
    neighbourhood: str,
    *,
    city: str = "",
    limit: int = 500,
) -> list[ValuationResult]:
    """Batch revaluation of a district (the agent desk's "refresh radar" action)."""
    query = select(Property).where(
        Property.neighborhood == neighbourhood,
        Property.status == PropertyStatus.ACTIVE,
    )
    if city:
        query = query.where(Property.city == city)
    rows = (await session.exec(query.limit(limit))).all()
    return [await value_property(session, row) for row in rows]


async def find_bargains(
    session: AsyncSession,
    *,
    neighbourhood: str | None = None,
    city: str | None = None,
    limit: int = 50,
) -> list[Property]:
    """Listings the engine flagged as below market -- the bargain radar feed."""
    query = select(Property).where(
        Property.valuation_status == ValuationStatus.BARGAIN,
        Property.status == PropertyStatus.ACTIVE,
    )
    if neighbourhood:
        query = query.where(Property.neighborhood == neighbourhood)
    if city:
        query = query.where(Property.city == city)
    return list((await session.exec(query.limit(limit))).all())


def bedroom_bucket(rooms: int | None) -> int:
    """``0`` for studios, ``4`` for 4+ bedrooms -- keeps cohorts populated."""
    if not rooms or rooms <= 0:
        return 0
    return min(rooms, 4)


def label_for(deviation_pct: float) -> ValuationStatus:
    if deviation_pct <= BARGAIN_THRESHOLD_PCT:
        return ValuationStatus.BARGAIN
    if deviation_pct > OVERPRICED_THRESHOLD_PCT:
        return ValuationStatus.OVERPRICED
    return ValuationStatus.FAIR


# --------------------------------------------------------------------- events
async def value_ingested_property(
    session: AsyncSession | None = None,
    property_id: uuid.UUID | None = None,
    **_: Any,
) -> ValuationResult | None:
    """Event-bus handler for ``NewPropertyIngested``.

    A crawled listing would otherwise sit at ``UNKNOWN`` forever, so the radar
    could never see it.  Valuing it at ingest closes that gap.  Mirrors
    :func:`app.services.matching_service.handle_new_property`: reuse the
    publisher's session when given, else open a short-lived one.

    The name is deliberately distinct from the matching handler so the two
    subscriptions' idempotency checks cannot shadow each other.
    """
    if property_id is None:
        return None
    if session is not None:
        return await _value_with_session(session, property_id)
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as own_session:
        return await _value_with_session(own_session, property_id)


async def _value_with_session(
    session: AsyncSession, property_id: uuid.UUID
) -> ValuationResult | None:
    prop = await session.get(Property, property_id)
    if prop is None:
        logger.warning("valuation requested for missing property %s", property_id)
        return None
    return await value_property(session, prop)


def register_valuation_subscriber() -> bool:
    """Subscribe the AVM to ``NewPropertyIngested`` (idempotent)."""
    existing = event_bus.handlers_for(NEW_PROPERTY_INGESTED)
    if any(
        getattr(h, "__name__", "") == "value_ingested_property" for h in existing
    ):
        return False
    event_bus.subscribe(NEW_PROPERTY_INGESTED, value_ingested_property)
    logger.info("valuation subscriber registered")
    return True


def unregister_valuation_subscriber() -> None:
    event_bus.unsubscribe(NEW_PROPERTY_INGESTED, value_ingested_property)


__all__ = [
    "ValuationResult",
    "build_cohort",
    "value_property",
    "value_neighbourhood",
    "find_bargains",
    "bedroom_bucket",
    "label_for",
    "value_ingested_property",
    "register_valuation_subscriber",
    "unregister_valuation_subscriber",
]