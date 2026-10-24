"""Direct (first-party) property submission with an OSM-resolved pin.

The scraper is only one ingestion channel; an owner or an advisor registering
their own unit is a *first-class* one. This service owns that path: it resolves
the dropped pin through OpenStreetMap (reverse geocoding, cached per
grid cell), dedupes against what we already hold, writes the owner contacts into
the encrypted vault, and opens the price-history row so later edits stay
traceable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import Settings
from app.core.crypto import PiiCipher
from app.core.logging import get_logger
from app.models import Property, PropertyOwnerPII, PropertyPriceHistory
from app.models.enums import (
    DealType,
    PriceChangeSource,
    PropertySource,
    PropertyStatus,
    PropertyType,
    SubmitterType,
)
from app.services.ingestion.deduplicator import compute_content_hash, precedence_for
from app.services.ingestion.sanitizer import to_ewkt_point

logger = get_logger("app.submission")

# Iran bounding box -- a pin outside it is a mistake, not a listing.
LAT_MIN, LAT_MAX = 25.0, 40.5
LNG_MIN, LNG_MAX = 44.0, 64.5

# Two units this close with matching specs are the same door.
NEAR_DUPLICATE_RADIUS_M = 50


@dataclass
class SubmissionResult:
    """Outcome of one direct submission."""

    property_id: uuid.UUID
    created: bool
    district: str = ""
    valuation_status: str = ""


def validate_pin(latitude: float, longitude: float) -> None:
    """Raise ``ValueError`` for a coordinate pair that cannot be an Iranian pin."""
    if not (LAT_MIN <= latitude <= LAT_MAX and LNG_MIN <= longitude <= LNG_MAX):
        raise ValueError("pin_out_of_range")


def source_for(submitter_type: SubmitterType | None) -> PropertySource:
    """The provenance channel a submitter class registers under.

    Two members rather than one bucket, because the two first-party classes are
    genuinely different trust levels: ``INTERNAL_USER`` (100) outranks
    ``INTERNAL_AGENCY`` (80) in ``SOURCE_PRECEDENCE``, so the deduplicator can
    prefer the owner's own copy of a unit over the office's. Collapsing them
    would leave the «ثبت ملک» badge and that ranking with nothing to key off.
    """
    if submitter_type is SubmitterType.PERSON:
        return PropertySource.INTERNAL_USER
    return PropertySource.INTERNAL_AGENCY


async def reverse_geocode(
    session: AsyncSession, latitude: float, longitude: float, settings: Settings
) -> dict[str, str]:
    """Resolve a pin to Persian administrative names via the configured geocoder.

    The node must stay usable offline, so an unreachable geocoder degrades to an
    empty result instead of failing the submission.
    """
    from app.services.geo import reverse_geocode as geo_reverse

    try:
        return await geo_reverse(session, latitude, longitude, settings)
    except Exception as exc:  # network, parse, or geocoder disabled
        logger.warning("reverse geocode failed for %s,%s: %s", latitude, longitude, exc)
        return {}


def specs_match(
    candidate: Property,
    *,
    area: float | None,
    rooms: int | None,
    property_type: PropertyType | None,
) -> bool:
    """Area within 3%, same room count, same property type."""
    if property_type and candidate.property_type is not property_type:
        return False
    if area and candidate.area:
        if not (area * 0.97 <= candidate.area <= area * 1.03):
            return False
    if rooms is not None and candidate.rooms is not None and candidate.rooms != rooms:
        return False
    return True


async def find_nearby(
    session: AsyncSession,
    *,
    latitude: float,
    longitude: float,
    radius_m: int = NEAR_DUPLICATE_RADIUS_M,
    limit: int = 25,
) -> list[tuple[Property, float]]:
    """Active properties within ``radius_m`` of the pin, closest first."""
    from app.services.geo import point_distance_m

    rows = (
        await session.exec(
            select(Property).where(
                Property.status == PropertyStatus.ACTIVE,
                Property.latitude.is_not(None),
                Property.longitude.is_not(None),
            ).limit(500)
        )
    ).all()

    scored = [
        (row, point_distance_m(latitude, longitude, row.latitude or 0.0, row.longitude or 0.0))
        for row in rows
    ]
    return sorted(
        (item for item in scored if item[1] <= radius_m), key=lambda item: item[1]
    )[:limit]


async def record_price(
    session: AsyncSession,
    property_: Property,
    *,
    new_price: int,
    source: PriceChangeSource,
    source_ref: str | None = None,
    created_by_id: uuid.UUID | None = None,
) -> PropertyPriceHistory | None:
    """Append a price-history row when the price actually moved.

    Re-submitting the same price is a no-op, which keeps ingestion idempotent.
    """
    previous = property_.total_price
    if not new_price or new_price == previous:
        return None
    difference = new_price - (previous or 0)
    entry = PropertyPriceHistory(
        property_id=property_.id,
        previous_price=previous,
        new_price=new_price,
        price_difference=difference,
        change_percentage=(100.0 * difference / previous) if previous else 0.0,
        source=source,
        source_ref=source_ref,
        created_by_id=created_by_id,
    )
    session.add(entry)
    property_.total_price = new_price
    if property_.area:
        property_.price_per_meter = int(new_price / property_.area)
    session.add(property_)
    return entry


async def upsert_owner_pii(
    session: AsyncSession,
    *,
    property_id: uuid.UUID,
    cipher: PiiCipher,
    owner_name: str | None = None,
    owner_phone: str | None = None,
    created_by_id: uuid.UUID | None = None,
) -> PropertyOwnerPII:
    """Write owner contacts to the encrypted vault with searchable blind indexes."""
    row = (
        await session.exec(
            select(PropertyOwnerPII).where(PropertyOwnerPII.property_id == property_id)
        )
    ).first() or PropertyOwnerPII(property_id=property_id)

    if owner_name:
        row.owner_name_enc = cipher.encrypt(owner_name)
        row.owner_name_bindex = cipher.blind_index(owner_name)
    if owner_phone:
        row.owner_phone_enc = cipher.encrypt(owner_phone)
        row.owner_phone_bindex = cipher.blind_index(owner_phone)
    if created_by_id is not None:
        row.created_by_id = created_by_id

    session.add(row)
    return row


async def submit_property(
    session: AsyncSession,
    *,
    latitude: float,
    longitude: float,
    deal_type: DealType,
    property_type: PropertyType,
    title: str = "",
    description: str = "",
    area: float | None = None,
    rooms: int | None = None,
    floor: int | None = None,
    total_floors: int | None = None,
    year_built: int | None = None,
    total_price: int | None = None,
    deposit_amount: int | None = None,
    monthly_rent: int | None = None,
    has_elevator: bool = False,
    has_parking: bool = False,
    has_storage: bool = False,
    has_balcony: bool = False,
    owner_name: str | None = None,
    owner_phone: str | None = None,
    settings: Settings | None = None,
    cipher: PiiCipher | None = None,
    created_by_id: uuid.UUID | None = None,
    #: Who pressed submit. Set by the endpoint from the signed token, never from
    #: the request body -- see ``app.models.enums.SUBMITTER_TYPE_BY_ROLE``. Left
    #: ``None`` only by internal callers (backfills, tests) that have no caller
    #: to attribute, and those rows honestly read as "unknown" rather than
    #: being guessed into a bucket.
    submitter_type: SubmitterType | None = None,
) -> SubmissionResult:
    """Create or update a property from a first-party submission.

    ``created`` distinguishes a genuinely new listing from one that merged into
    an existing record (the same unit re-posted by a second advisor).
    """
    from app.core.config import get_settings
    from app.services import valuation

    settings = settings or get_settings()
    cipher = cipher or PiiCipher.from_key_file(settings.resolve_path(settings.pii_key_file))
    validate_pin(latitude, longitude)

    located = await reverse_geocode(session, latitude, longitude, settings)
    district = located.get("neighborhood") or located.get("district") or ""
    # Same City Gate guard as the scraper sanitiser: reverse-geocode can return
    # a district in the city slot on edge pins, which would orphan the row from
    # every city filter. Non-cities fall back to neighborhood.
    from app.services.city_normalizer import normalize_city_neighborhood

    located_city, _ = normalize_city_neighborhood(located.get("city"), district)
    located = {**located, "city": located_city}
    content_hash = compute_content_hash(located.get("city"), district, area, floor, total_price)

    # 1) Exact structural fingerprint match (the same unit re-posted).
    existing = None
    if content_hash:
        existing = (
            await session.exec(select(Property).where(Property.content_hash == content_hash))
        ).first()

    # 2) Otherwise a spatial + specs match inside the near-duplicate radius.
    if existing is None:
        for candidate, _distance in await find_nearby(
            session, latitude=latitude, longitude=longitude
        ):
            if specs_match(candidate, area=area, rooms=rooms, property_type=property_type):
                existing = candidate
                break

    created = existing is None
    if existing is None:
        existing = Property(
            title=title or district or "فهرست جدید",
            description=description,
            property_type=property_type,
            deal_type=deal_type,
            status=PropertyStatus.ACTIVE,
            # Provenance. A natural person filing their own unit outranks an
            # office filing a client's, so the two first-party channels are
            # separate members rather than one bucket -- otherwise the
            # deduplicator cannot prefer the owner's copy, and the «ثبت مالک»
            # badge has nothing to render.
            source=source_for(submitter_type),
            # Snapshotted, not looked up later: the class of party that filed it
            # is a fact about the write, not about the account as it stands now.
            submitter_type=submitter_type,
            storage_node_id="local",
            content_hash=content_hash,
            created_by_id=created_by_id,
        )
    elif submitter_type is not None:
        # A merge into an existing row. Both provenance fields follow the rule
        # ``SOURCE_PRECEDENCE`` states: the higher-precedence writer wins, so a
        # genuine owner registering their own unit upgrades an office record
        # rather than being absorbed by it. Neither field is ever *downgraded*,
        # which is the same monotonic rule the deduplicator applies to the
        # canonical fields.
        #
        # A scraped row (submitter_type None, source from a portal) is left
        # alone: it has no submitter to classify, and guessing one from the
        # portal it came from would be a fabrication.
        incoming = source_for(submitter_type)
        if existing.submitter_type is None:
            existing.submitter_type = submitter_type
        if precedence_for(incoming) > precedence_for(existing.source):
            existing.source = incoming
            existing.submitter_type = submitter_type
    existing.latitude = latitude
    existing.longitude = longitude
    existing.location = to_ewkt_point(latitude, longitude)
    existing.province = located.get("province") or existing.province or ""
    existing.city = located.get("city") or existing.city or ""
    existing.neighborhood = district or existing.neighborhood
    if area is not None:
        existing.area = area
    if rooms is not None:
        existing.rooms = rooms
    if floor is not None:
        existing.floor = floor
    if total_floors is not None:
        existing.total_floors = total_floors
    if year_built is not None:
        existing.year_built = year_built
    if deposit_amount is not None:
        existing.deposit_amount = deposit_amount
    if monthly_rent is not None:
        existing.monthly_rent = monthly_rent
    existing.has_elevator = has_elevator
    existing.has_parking = has_parking
    existing.has_storage = has_storage
    existing.has_balcony = has_balcony
    if title:
        existing.title = title
    if description:
        existing.description = description

    # The price-history row says *who announced the figure*, which is not the
    # same as who typed it in: a broker filing an owner's asking price is a
    # ``MANUAL`` edit, not the owner's own entry. Hard-coding OWNER here made
    # every listing claim the owner set the price.
    await record_price(
        session,
        existing,
        new_price=total_price or 0,
        source=(
            PriceChangeSource.OWNER
            if submitter_type is SubmitterType.PERSON
            else PriceChangeSource.MANUAL
        ),
    )
    if existing.area and existing.total_price:
        existing.price_per_meter = int(existing.total_price / existing.area)

    if owner_name or owner_phone:
        await upsert_owner_pii(
            session,
            property_id=existing.id,
            cipher=cipher,
            owner_name=owner_name,
            owner_phone=owner_phone,
            created_by_id=created_by_id,
        )

    session.add(existing)
    await session.commit()
    await session.refresh(existing)

    result = await valuation.value_property(session, existing)
    logger.info(
        "direct submit property=%s created=%s district=%s valuation=%s",
        existing.id, created, district, result.status.value,
    )
    return SubmissionResult(
        property_id=existing.id,
        created=created,
        district=district,
        valuation_status=result.status.value,
    )