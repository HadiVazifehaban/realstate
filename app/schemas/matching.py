"""Pydantic schemas for Phase 3 matching (demands + suggestion queue)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ClientDemandCreate(BaseModel):
    """Body for ``POST /api/v1/matching/demands``."""

    client_name: str = Field(default="", max_length=255)
    client_phone: str = Field(default="", max_length=32)
    client_phone_alt: str = Field(default="", max_length=32)
    notes: str = Field(default="")
    deal_type: str = Field(default="SALE")
    priority: int = Field(default=0)
    min_area: float | None = None
    max_area: float | None = None
    min_rooms: int | None = None
    max_rooms: int | None = None
    max_building_age: int | None = None
    requires_elevator: bool = False
    requires_parking: bool = False
    requires_storage: bool = False
    preferred_types: str = Field(default="")
    min_total_price: int | None = None
    max_total_price: int | None = None
    min_deposit: int | None = None
    max_deposit: int | None = None
    max_monthly_rent: int | None = None
    target_neighborhoods: str = Field(default="")
    center_lat: float | None = None
    center_lng: float | None = None
    radius_meters: int | None = None


class ClientDemandUpdate(BaseModel):
    """Partial update for ``PATCH /api/v1/matching/demands/{id}``."""

    client_name: str | None = None
    client_phone: str | None = None
    client_phone_alt: str | None = None
    notes: str | None = None
    deal_type: str | None = None
    status: str | None = None
    priority: int | None = None
    min_area: float | None = None
    max_area: float | None = None
    min_rooms: int | None = None
    max_rooms: int | None = None
    max_building_age: int | None = None
    requires_elevator: bool | None = None
    requires_parking: bool | None = None
    requires_storage: bool | None = None
    preferred_types: str | None = None
    min_total_price: int | None = None
    max_total_price: int | None = None
    min_deposit: int | None = None
    max_deposit: int | None = None
    max_monthly_rent: int | None = None
    target_neighborhoods: str | None = None
    center_lat: float | None = None
    center_lng: float | None = None
    radius_meters: int | None = None


class ClientDemandResponse(BaseModel):
    """One demand row."""

    id: uuid.UUID
    client_name: str = ""
    client_phone: str = ""
    deal_type: str
    status: str
    priority: int = 0
    min_area: float | None = None
    max_area: float | None = None
    min_rooms: int | None = None
    max_rooms: int | None = None
    min_total_price: int | None = None
    max_total_price: int | None = None
    max_monthly_rent: int | None = None
    center_lat: float | None = None
    center_lng: float | None = None
    radius_meters: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_demand(cls, demand) -> "ClientDemandResponse":
        def _v(v):
            return v.value if hasattr(v, "value") else str(v)

        return cls(
            id=demand.id,
            client_name=demand.client_name or "",
            client_phone=demand.client_phone or "",
            deal_type=_v(demand.deal_type),
            status=_v(demand.status),
            priority=demand.priority or 0,
            min_area=demand.min_area,
            max_area=demand.max_area,
            min_rooms=demand.min_rooms,
            max_rooms=demand.max_rooms,
            min_total_price=demand.min_total_price,
            max_total_price=demand.max_total_price,
            max_monthly_rent=demand.max_monthly_rent,
            center_lat=demand.center_lat,
            center_lng=demand.center_lng,
            radius_meters=demand.radius_meters,
            created_at=demand.created_at,
            updated_at=demand.updated_at,
        )


class ClientDemandListResponse(BaseModel):
    """Paginated demands."""

    items: list[ClientDemandResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


class PropertyMatchResponse(BaseModel):
    """One scored suggestion."""

    id: uuid.UUID
    property_id: uuid.UUID
    demand_id: uuid.UUID
    score: float = 0.0
    geo_score: float = 0.0
    price_score: float = 0.0
    specs_score: float = 0.0
    breakdown: dict[str, Any] = Field(default_factory=dict)
    status: str
    distance_meters: float | None = None
    property_title: str = ""
    demand_name: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_match(cls, match, *, property_title: str = "", demand_name: str = "") -> "PropertyMatchResponse":
        def _v(v):
            return v.value if hasattr(v, "value") else str(v)

        return cls(
            id=match.id,
            property_id=match.property_id,
            demand_id=match.demand_id,
            score=match.score,
            geo_score=match.geo_score,
            price_score=match.price_score,
            specs_score=match.specs_score,
            breakdown=dict(match.breakdown or {}),
            status=_v(match.status),
            distance_meters=match.distance_meters,
            property_title=property_title,
            demand_name=demand_name,
            created_at=match.created_at,
            updated_at=match.updated_at,
        )


class PropertyMatchListResponse(BaseModel):
    """Paginated matches."""

    items: list[PropertyMatchResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


class MatchStatusUpdate(BaseModel):
    """Body for ``PATCH /api/v1/matching/matches/{id}``."""

    status: str = Field(description="NEW | SEEN | SHORTLISTED | DISMISSED | CONTACTED")


class RetriggerResponse(BaseModel):
    """Result of ``POST /api/v1/matching/demands/{id}/retrigger``."""

    demand_id: uuid.UUID
    matches_created: int = 0
    matches_updated: int = 0


__all__ = [
    "ClientDemandCreate",
    "ClientDemandUpdate",
    "ClientDemandResponse",
    "ClientDemandListResponse",
    "PropertyMatchResponse",
    "PropertyMatchListResponse",
    "MatchStatusUpdate",
    "RetriggerResponse",
]
