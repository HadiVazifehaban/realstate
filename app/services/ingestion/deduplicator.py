"""De-duplication for ingested listings (Phase 4).

Three independent guards:

1. **External identity** — the portal ``token`` (``external_id``) is globally
   unique; a re-scrape updates rather than duplicates.
2. **Content fingerprint** — ``SHA256(city + district + area + floor +
   rounded_price)`` collapses the same physical unit re-posted by different
   advisors at a slightly different price.
3. **Spatial + spec proximity** — the guard that actually matters for a
   map-first platform. ``score_candidate`` scores candidates inside a radius on
   distance/area/beds/floor/phone and returns a confidence, so the caller can
   auto-merge high-confidence hits and quarantine the ambiguous band for a
   supervisor instead of silently creating a second record for one flat.

Provenance decides who wins: when the incoming listing outranks the existing
one (see ``SOURCE_PRECEDENCE``), the existing canonical fields are overwritten.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Property
from app.models.enums import (
    LEGACY_SOURCE_ALIASES,
    SOURCE_PRECEDENCE,
    PropertySource,
)

DEFAULT_PRICE_ROUNDING = 10_000_000  # round to the nearest 10 million Toman

# -- Spatial matching parameters (Phase 4) -------------------------------------
#: Candidate retrieval radius. Two units further apart than this are different
#: units, so nothing outside it is ever scored.
DEFAULT_DEDUP_RADIUS_M = 50.0
#: Area tolerance. 3% absorbs measurement/rounding noise without merging a
#: 90 m² studio with a 120 m² two-bed in the same building.
DEFAULT_AREA_TOLERANCE = 0.03
#: At/above this confidence a match is merged automatically. Below
#: QUARANTINE_CONFIDENCE the honest answer is "different unit", so a new record
#: is created rather than padding a supervisor's review queue.
AUTO_MERGE_CONFIDENCE = 0.78
QUARANTINE_CONFIDENCE = 0.62

#: Component weights; they sum to 1.0 so a confidence reads directly as
#: "how much of the match is explained".
W_GEO = 0.35
W_AREA = 0.20
W_BEDS = 0.15
W_FLOOR = 0.05
W_PHONE = 0.20
W_MEDIA = 0.05


def canonical_source(source: PropertySource) -> PropertySource:
    """Map a legacy source onto its modern equivalent."""
    return LEGACY_SOURCE_ALIASES.get(source, source)


def precedence_for(source: PropertySource) -> int:
    """Numeric provenance score for a source (higher wins)."""
    return SOURCE_PRECEDENCE.get(canonical_source(source), 0)


@dataclass(frozen=True)
class DuplicateMatch:
    """A scored candidate plus the evidence behind the score.

    Exposed so the admin API can show *why* two listings were linked and a
    supervisor can overturn a wrong merge.
    """

    property: Property
    confidence: float
    distance_m: float
    reasons: dict[str, float]


def compute_content_hash(
    city: str | None,
    district: str | None,
    area: float | None,
    floor: int | None,
    price: int | None,
    *,
    price_rounding: int = DEFAULT_PRICE_ROUNDING,
) -> str:
    """Deterministic structural fingerprint for a listing."""
    rounded_price = ""
    if price:
        step = max(int(price_rounding), 1)
        rounded_price = str(round(price / step) * step)
    parts = [
        (city or "").strip().casefold(),
        (district or "").strip().casefold(),
        str(int(area)) if area else "",
        str(floor) if floor is not None else "",
        rounded_price,
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


async def find_by_external_id(
    session: AsyncSession, external_id: str | None
) -> Property | None:
    if not external_id:
        return None
    result = await session.exec(select(Property).where(Property.external_id == external_id))
    return result.first()


async def find_by_content_hash(
    session: AsyncSession, content_hash: str | None
) -> Property | None:
    if not content_hash:
        return None
    result = await session.exec(
        select(Property).where(Property.content_hash == content_hash)
    )
    return result.first()


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres.

    Implemented locally rather than through PostGIS so scoring stays unit
    testable and runs against the SQLite-backed suite; PostGIS still does the
    index-backed candidate retrieval in production.
    """
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def score_candidate(
    incoming: Property,
    candidate: Property,
    *,
    distance_m: float | None = None,
    radius_m: float = DEFAULT_DEDUP_RADIUS_M,
    phone_blind_index: str | None = None,
    candidate_phone_blind_index: str | None = None,
    media_similarity: float = 0.0,
) -> DuplicateMatch | None:
    """Weighted 0..1 confidence that two records describe the same unit.

    Returns ``None`` when a hard gate rejects the pair (different deal type,
    property type, out of radius, or area far outside tolerance). A low score is
    a judgement call; a gate breach is a certainty, and gating early keeps the
    ambiguity band meaningful.
    """
    if incoming.deal_type != candidate.deal_type:
        return None
    if incoming.property_type != candidate.property_type:
        return None

    if distance_m is None:
        if (
            incoming.latitude is None
            or incoming.longitude is None
            or candidate.latitude is None
            or candidate.longitude is None
        ):
            return None
        distance_m = haversine_m(
            incoming.latitude,
            incoming.longitude,
            candidate.latitude,
            candidate.longitude,
        )

    if distance_m > radius_m:
        return None

    reasons: dict[str, float] = {}

    # Geometry: 1.0 at the same point, decaying linearly to 0 at the radius edge.
    s_geo = max(0.0, 1.0 - (distance_m / radius_m))
    reasons["geo"] = s_geo

    # Area: relative closeness, only when both sides reported a size.
    s_area = 0.0
    if incoming.area and candidate.area:
        rel = abs(incoming.area - candidate.area) / max(incoming.area, candidate.area)
        if rel > DEFAULT_AREA_TOLERANCE * 2:
            return None
        s_area = max(0.0, 1.0 - rel / (DEFAULT_AREA_TOLERANCE * 2))
    reasons["area"] = s_area

    # Beds: an exact match is strong evidence, a mismatch halves it.
    s_beds = 1.0 if incoming.rooms == candidate.rooms else 0.5
    reasons["beds"] = s_beds

    # Floor is a weak signal: the same unit is often re-posted with the floor
    # omitted entirely, so "unknown" sits mid-scale rather than at zero.
    s_floor = 0.5 if (incoming.floor is None or candidate.floor is None) else (
        1.0 if incoming.floor == candidate.floor else 0.4
    )
    reasons["floor"] = s_floor

    # An identical HMAC blind index is near-conclusive that one owner posted
    # both. Comparing the index never requires decrypting the number.
    s_phone = (
        1.0
        if phone_blind_index and phone_blind_index == candidate_phone_blind_index
        else 0.0
    )
    reasons["phone"] = s_phone

    # Perceptual-hash media similarity supplied by the caller (0..1).
    s_media = max(0.0, min(1.0, media_similarity))
    reasons["media"] = s_media

    confidence = (
        W_GEO * s_geo
        + W_AREA * s_area
        + W_BEDS * s_beds
        + W_FLOOR * s_floor
        + W_PHONE * s_phone
        + W_MEDIA * s_media
    )
    return DuplicateMatch(
        property=candidate,
        confidence=round(confidence, 4),
        distance_m=round(distance_m, 2),
        reasons={key: round(value, 4) for key, value in reasons.items()},
    )


async def find_duplicate(
    session: AsyncSession,
    *,
    external_id: str | None,
    content_hash: str | None,
) -> Property | None:
    """Return an existing property that matches by id or content fingerprint."""
    existing = await find_by_external_id(session, external_id)
    if existing is not None:
        return existing
    return await find_by_content_hash(session, content_hash)


async def find_spatial_duplicate(
    session: AsyncSession,
    incoming: Property,
    *,
    radius_m: float = DEFAULT_DEDUP_RADIUS_M,
    phone_blind_index: str | None = None,
) -> DuplicateMatch | None:
    """Best scoring candidate within ``radius_m`` of ``incoming``.

    Returns ``None`` when nothing is close enough, or when the best candidate
    falls under :data:`QUARANTINE_CONFIDENCE`.
    """
    if incoming.latitude is None or incoming.longitude is None:
        return None

    # Bounding-box prefilter narrows the scan; `score_candidate` applies the
    # exact radius test. Keeping the query portable lets the same logic run
    # against the SQLite test database.
    lat_delta = radius_m / 111_320.0
    lon_delta = radius_m / (
        111_320.0 * max(math.cos(math.radians(incoming.latitude)), 1e-6)
    )
    candidates = (
        await session.exec(
            select(Property)
            .where(
                Property.id != incoming.id,
                Property.deal_type == incoming.deal_type,
                Property.latitude.between(
                    incoming.latitude - lat_delta, incoming.latitude + lat_delta
                ),
                Property.longitude.between(
                    incoming.longitude - lon_delta, incoming.longitude + lon_delta
                ),
            )
            .limit(200)
        )
    ).all()

    best: DuplicateMatch | None = None
    for candidate in candidates:
        match = score_candidate(
            incoming,
            candidate,
            radius_m=radius_m,
            phone_blind_index=phone_blind_index,
        )
        if match is not None and (best is None or match.confidence > best.confidence):
            best = match

    if best is None or best.confidence < QUARANTINE_CONFIDENCE:
        return None
    return best

