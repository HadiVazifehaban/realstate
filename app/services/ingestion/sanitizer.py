"""Sanitiser: map a parsed :class:`DivarListingDetail` onto domain models.

Public fields go to ``Property``; sensitive owner fields go to the encrypted
``PropertyOwnerPII`` vault (Phase 1).  Coordinates are converted to PostGIS
``POINT(lng lat)`` EWKT at SRID 4326.
"""

from __future__ import annotations

from typing import Any

from app.models.enums import DealType, PropertySource
from app.services.city_normalizer import normalize_city_neighborhood
from app.services.location_catalog import resolve_city
from app.services.scraper.parser import DivarListingDetail


def to_ewkt_point(lat: float | None, lng: float | None) -> str | None:
    """Build a PostGIS EWKT point literal (note: longitude first)."""
    if lat is None or lng is None:
        return None
    return f"SRID=4326;POINT({lng} {lat})"


def _agency_name(detail: DivarListingDetail) -> str | None:
    """Agency name, falling back to the agent for a personal listing.

    A listing published by one person has no agency; showing the person's name
    in the agency slot would imply a firm that does not exist, so this stays
    None and the card renders the agent alone.
    """
    return detail.agency_name or None


def _agency_slug(detail: DivarListingDetail) -> str | None:
    return detail.agency_slug or None


def build_property_fields(
    detail: DivarListingDetail,
    *,
    content_hash: str | None,
    storage_node_id: str = "local",
    source: PropertySource = PropertySource.DIVAR_SCRAPER,
) -> dict[str, Any]:
    """Public, owner-free fields for the ``Property`` model."""
    # The persisted legacy schema requires a concrete enum. Never turn a
    # combined/unknown source category into APARTMENT: only detail evidence may
    # supply the type. When absent, omit the key so legacy callers/model schema
    # default behavior remains unchanged rather than asserting guessed evidence.
    #
    # City Gate guard: the parser's city slot sometimes carries a neighbourhood
    # (``پونک``), a phase (``فاز ۱``) or a street -- those rows would vanish the
    # moment a user picks a real city, so non-cities are demoted to neighborhood.
    city, neighborhood = normalize_city_neighborhood(
        detail.city, detail.neighborhood or detail.district
    )
    located = resolve_city(city, detail.province)
    fields: dict[str, Any] = {
        "title": detail.title or "",
        "description": detail.description or "",
        **({"property_type": detail.property_type} if detail.property_type is not None else {}),
        "deal_type": detail.deal_type or DealType.SALE,
        "province": located["province"] if located else "",
        "city": located["name"] if located else city,
        "neighborhood": neighborhood,
        "area": detail.area,
        "land_area": detail.land_area,
        "rooms": detail.rooms,
        "year_built": detail.year_built,
        "floor": detail.floor,
        "total_floors": detail.total_floors,
        "units_per_floor": detail.units_per_floor,
        "has_elevator": bool(detail.has_elevator),
        "has_parking": bool(detail.has_parking),
        "has_storage": bool(detail.has_storage),
        "has_balcony": bool(detail.has_balcony),
        "price_per_meter": detail.price_per_meter,
        "total_price": detail.total_price,
        "deposit_amount": detail.deposit,
        "monthly_rent": detail.monthly_rent,
        "source": source,
        "source_ref": detail.token,
        "external_id": detail.token,
        # Business identity for the advisor card. Divar's contact block and
        # Delta's offeredBy/realEstateAgency both land here; null when the source
        # names nobody, which the card renders as "not stated" rather than a
        # fabricated agent.
        "agent_name": detail.agent_name,
        "agency_name": _agency_name(detail),
        "agency_slug": _agency_slug(detail),
        "content_hash": content_hash,
        "raw_data": detail.raw,
        "is_shared_to_mls": False,
        "storage_node_id": storage_node_id,
    }
    location = to_ewkt_point(detail.latitude, detail.longitude)
    if location is not None:
        fields["location"] = location
    # The scalar pair is what the API projects and the map picker reads; keeping
    # only the geometry column left every listing pin-less in the UI.
    fields["latitude"] = detail.latitude
    fields["longitude"] = detail.longitude
    return fields


def build_owner_pii_fields(detail: DivarListingDetail) -> dict[str, str | None]:
    """Plaintext owner fields, to be encrypted before persisting."""
    return {
        "owner_phone": detail.phone,
        # Divar never exposes the owner name; kept for manual enrichment.
        "owner_name": None,
    }
