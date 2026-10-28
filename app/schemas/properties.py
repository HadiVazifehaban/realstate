"""Schemas for first-party property submission and valuation (Phase 3b)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    DealType,
    MediaType,
    PriceChangeSource,
    PropertySource,
    PropertyStatus,
    PropertyType,
    SubmitterType,
    ValuationStatus,
    VisitSlotKind,
    VisitSlotStatus,
)
from app.services.geo import PRIVACY_BLUR_RADIUS_M

# Iran bounding box, mirrored from the service so invalid pins fail fast at the
# edge with a 422 instead of reaching the geocoder.
LAT_MIN, LAT_MAX = 25.0, 40.5
LNG_MIN, LNG_MAX = 44.0, 64.5


class PropertySubmitRequest(BaseModel):
    """A unit registered by an owner or advisor with an OSM pin."""

    latitude: float = Field(ge=LAT_MIN, le=LAT_MAX, description="عرض جغرافیایی پین")
    longitude: float = Field(ge=LNG_MIN, le=LNG_MAX, description="طول جغرافیایی پین")

    property_type: PropertyType = PropertyType.APARTMENT
    deal_type: DealType = DealType.SALE

    title: str = Field(default="", max_length=255)
    description: str = Field(default="")

    area: float | None = Field(default=None, gt=0, le=100_000)
    rooms: int | None = Field(default=None, ge=0, le=30)
    floor: int | None = Field(default=None, ge=-5, le=100)
    total_floors: int | None = Field(default=None, ge=0, le=100)
    year_built: int | None = Field(default=None, ge=1300, le=2100)

    total_price: int | None = Field(default=None, ge=0, description="قیمت کل (تومان)")
    deposit_amount: int | None = Field(default=None, ge=0, description="ودیعه (تومان)")
    monthly_rent: int | None = Field(default=None, ge=0, description="اجاره ماهانه (تومان)")

    has_elevator: bool = False
    has_parking: bool = False
    has_storage: bool = False
    has_balcony: bool = False

    # Owner contacts go straight into the encrypted vault, never to `property`.
    owner_name: str | None = Field(default=None, max_length=255)
    owner_phone: str | None = Field(default=None, max_length=32)

    # There is deliberately **no** `submitter_type` here. The class of party
    # that filed the listing comes from the signed token (see
    # `app.core.identity.submitter_type_for`), because a body-supplied value
    # would let an office file as a private owner and inherit the owner's
    # provenance ranking. Extra keys are ignored rather than rejected, so an
    # older client that still sends one keeps working -- the value is simply
    # never read.

    @field_validator("total_price", "deposit_amount", "monthly_rent")
    @classmethod
    def _non_negative(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("amount must not be negative")
        return value

    def model_post_init(self, _context: object) -> None:
        if self.deal_type is DealType.RENT and not (self.deposit_amount or self.monthly_rent):
            raise ValueError("rent listings need deposit_amount or monthly_rent")


class PropertySubmitResponse(BaseModel):
    """Result of a direct submission, including the engine's first verdict."""

    property_id: uuid.UUID
    created: bool = Field(description="false = merged into an existing listing")
    district: str = ""
    valuation_status: ValuationStatus = ValuationStatus.UNKNOWN


class ValuationResponse(BaseModel):
    """Explainable valuation verdict for one property."""

    property_id: uuid.UUID
    valuation_status: ValuationStatus
    deviation_pct: float | None = None
    median_price_per_meter: int | None = None
    sample_count: int = 0
    bargain: bool = False
    explain: dict = Field(default_factory=dict)


class PriceHistoryEntry(BaseModel):
    """One point on a property's price timeline."""

    id: uuid.UUID
    previous_price: int | None = None
    new_price: int
    price_difference: int
    change_percentage: float
    source: PriceChangeSource
    source_ref: str | None = None
    recorded_at: datetime


class PriceUpdateRequest(BaseModel):
    """Advisor price edit -- always lands in the price history."""

    new_price: int = Field(ge=0, description="قیمت جدید (تومان)")
    reason: str = Field(default="", max_length=255)


class PropertySummary(BaseModel):
    """Public-safe projection: no owner PII, no exact pin by default.

    Carries the presentation fields a listing card needs -- provenance, the
    technical specs, amenities and the rent split -- so the feed can render one
    card without a second request per row. Still no owner contact and still no
    schedule: an appointment lives on the CRM timeline.
    """

    id: uuid.UUID
    title: str
    property_type: PropertyType
    deal_type: DealType
    status: PropertyStatus
    neighborhood: str = ""
    city: str = ""
    area: float | None = None
    rooms: int | None = None
    total_price: int | None = None
    price_per_meter: int | None = None
    valuation_status: ValuationStatus = ValuationStatus.UNKNOWN
    valuation_deviation_pct: float | None = None
    # AVM benchmark the verdict was computed against (weighted median Toman/m²),
    # so the card can show the actual estimate beside the deviation instead of
    # only a percentage.
    valuation_median_price_per_meter: int | None = None
    valuation_sample_count: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    exact_pin: bool = Field(
        default=False, description="true only for an authorised in-office viewer"
    )
    privacy_radius_m: int = Field(
        default=int(PRIVACY_BLUR_RADIUS_M),
        description=(
            "Radius of the approximate area shown instead of the exact pin. "
            "Always sent so the map draws the circle the backend actually masks "
            "to, rather than a second hard-coded number in the client."
        ),
    )

    # -- Card presentation ------------------------------------------------------
    source: PropertySource = Field(
        default=PropertySource.MANUAL_OFFICE,
        description="Provenance badge; legacy values are aliased on read.",
    )
    #: Class of party that filed the row -- PERSON (شخص حقیقی) or AGENCY
    #: (بنگاه). Snapshotted from the submitter's token, so this is *not*
    #: inferred from ``source`` and never from the request body. Null for a
    #: scraped listing, which has no submitter to classify.
    submitter_type: SubmitterType | None = Field(
        default=None,
        description="نوع ثبت‌کننده در لحظهٔ ثبت — شخص حقیقی یا بنگاه",
    )
    #: Listed-by identity for the advisor card. Business, never the owner -- the
    #: owner's phone lives encrypted in the PII vault behind the reveal endpoint.
    agent_name: str | None = None
    agency_name: str | None = None
    #: Portal-side listing id, rendered as "کد ملک" on the detail page.
    source_ref: str | None = None
    floor: int | None = None
    total_floors: int | None = None
    year_built: int | None = None
    has_elevator: bool = False
    has_parking: bool = False
    has_storage: bool = False
    has_balcony: bool = False
    deposit_amount: int | None = Field(
        default=None, description="ودیعه / رهن — RENT and FULL_MORTGAGE only"
    )
    monthly_rent: int | None = Field(
        default=None, description="اجاره ماهانه — RENT only"
    )
    updated_at: datetime | None = Field(
        default=None, description="Last write; the card renders it as age"
    )
    #: Free-text listing body as published by the source. Empty for a listing
    #: registered without one. Carries no owner contact: the portals keep the
    #: seller's phone out of the description precisely so it can be republished.
    description: str = ""
    #: Cover image URL, when the node can actually serve one. Null rather than a
    #: LAN filesystem path, which the browser could not load.
    cover_url: str | None = None
    images_count: int = 0
    message_available: bool = False
    message_unavailable_reason: str | None = None
    contact_available: bool = False
    contact_unavailable_reason: str | None = None


class PublicListingDTO(BaseModel):
    """Explicit allowlist for a future public listing contract.

    This DTO is intentionally not wired to a route in Phase 1. Keeping it
    independent from ``PropertySummary`` prevents an internal response field
    from becoming public by inheritance or a later refactor.
    """

    model_config = ConfigDict(extra="forbid")

    public_id: uuid.UUID
    sanitized_title: str
    sanitized_description: str
    property_type: PropertyType
    deal_type: DealType
    neighborhood: str = ""
    city: str = ""
    area: float | None = None
    rooms: int | None = None
    total_price: int | None = None
    price_per_meter: int | None = None
    approximate_latitude: float | None = None
    approximate_longitude: float | None = None
    privacy_radius_m: int = int(PRIVACY_BLUR_RADIUS_M)
    has_elevator: bool = False
    has_parking: bool = False
    has_storage: bool = False
    has_balcony: bool = False
    deposit_amount: int | None = None
    monthly_rent: int | None = None


class PublicMediaDTO(BaseModel):
    """Allowlisted public derivative; never a local path or internal media ID."""

    model_config = ConfigDict(extra="forbid")

    public_media_id: uuid.UUID
    derivative_url: str
    media_type: MediaType
    sort_order: int = 0
    is_cover: bool = False


class PropertyMediaItem(BaseModel):
    """One servable image of a listing.

    Only ``url`` is exposed. ``local_path`` names a file on the office node's
    disk, which a browser on the LAN cannot fetch, so handing it out would render
    a broken image; such a row is skipped by the endpoint instead.
    """

    id: uuid.UUID
    url: str
    is_cover: bool = False
    media_type: MediaType = MediaType.IMAGE
    sort_order: int = 0


class PropertyMediaListResponse(BaseModel):
    """Full gallery for one listing, cover first."""

    property_id: uuid.UUID
    items: list[PropertyMediaItem]
    count: int = 0


class NearbyPoiItem(BaseModel):
    """One named amenity, with how far it is from the pin."""

    name: str
    lat: float
    lng: float
    distance_m: int = 0


class NearbyPoiResponse(BaseModel):
    """Bucketed amenities around a listing.

    Every bucket key is always present, even when empty, so the page renders a
    stable set of cards rather than a list that reflows as data arrives.
    """

    property_id: uuid.UUID
    radius_m: int
    buckets: dict[str, list[NearbyPoiItem]] = Field(default_factory=dict)


class PropertyReportCreate(BaseModel):
    """A "this listing is wrong" report from the detail page."""

    reason: str = Field(
        description="One of the report reasons the UI offers, e.g. 'wrong_price'."
    )
    detail: str | None = Field(default=None, max_length=2000)
    reporter_email: str | None = Field(default=None, max_length=255)

    @field_validator("reason")
    @classmethod
    def _known_reason(cls, value: str) -> str:
        from app.models.property_report import ReportReason

        if value not in ReportReason.ALL:
            raise ValueError(
                f"unknown report reason {value!r}; expected one of "
                f"{', '.join(ReportReason.ALL)}"
            )
        return value


class PropertyReportResponse(BaseModel):
    """Acknowledgement of a recorded report."""

    id: uuid.UUID
    reason: str


class ReverseGeocodeRequest(BaseModel):
    """Ask what the OSM pin resolves to before committing a submission."""

    latitude: float = Field(ge=LAT_MIN, le=LAT_MAX)
    longitude: float = Field(ge=LNG_MIN, le=LNG_MAX)


class ReverseGeocodeResponse(BaseModel):
    province: str = ""
    city: str = ""
    district: str = ""
    neighborhood: str = ""
    display_name: str = ""
    # -- Traffic / odd-even zone metadata, stored as provider metadata ---
    municipality_zone: str = ""
    formatted_address: str = ""
    in_traffic_zone: bool | None = None
    in_odd_even_zone: bool | None = None


class BargainListResponse(BaseModel):
    """Radar feed: listings the engine priced below the local market."""

    count: int
    items: list[PropertySummary]


class NeighbourhoodStat(BaseModel):
    """One neighbourhood's slice of the market (see ``app/services/market.py``).

    Carries no listing and no owner data: the map needs a name, a median and a
    place to draw the bubble, and shipping individual files here would leak the
    inventory behind a market summary.
    """

    neighborhood: str
    city: str = ""
    files: int = 0
    all_files: int = 0
    median_price_per_meter: int | None = None
    median_total_price: int | None = None
    median_deposit: int | None = None
    median_monthly_rent: int | None = None
    median_area: float | None = None
    bargain_share: float = 0.0
    median_deviation_pct: float | None = None
    latitude: float | None = None
    longitude: float | None = None


class NeighbourhoodMarketResponse(BaseModel):
    """City-level market view: the map's bubbles plus the totals behind them."""

    city: str | None = None
    deal_types: list[DealType] = Field(default_factory=list)
    count: int = 0
    total_files: int = 0
    priced_files: int = 0
    median_price_per_meter: int | None = None
    items: list[NeighbourhoodStat] = Field(default_factory=list)


class PropertyListResponse(BaseModel):
    """Live inventory feed: every listing the office node holds.

    Mirrors :class:`BargainListResponse` so the frontend can reuse one card
    component for both the full feed and the filtered radar.
    """

    count: int
    items: list[PropertySummary]
    limit: int
    offset: int


#: Slot states that keep a calendar window off the market. Anything else
#: (CANCELLED, NO_SHOW, COMPLETED) releases the window back to the scheduler:
#: the visitor never showed, the deal closed, so the next prospect may ask for
#: the same hour.

class DealSummaryItem(BaseModel):
    """One deal type's dashboard totals (purchase vs. rental)."""

    deal_type: DealType
    count: int
    value: int


class DealSummaryResponse(BaseModel):
    """Dashboard-facing deal totals for the overview charts."""

    deals: list[DealSummaryItem]


#: Slot states that keep a calendar window off the market.

BLOCKING_STATUSES: frozenset[VisitSlotStatus] = frozenset(
    {VisitSlotStatus.DRAFT, VisitSlotStatus.REQUESTED, VisitSlotStatus.CONFIRMED}
)



class VisitBookingCreate(BaseModel):
    """A visitor's request for one viewing window on a listing.

    The stored row always lands as ``REQUESTED`` -- a public request never
    confirms itself. Desk-side holds use :meth:`PropertyVisitBooking.draft_for`
    through the CRM, not this route.
    """

    slot_date: date = Field(description="روز بازدید (میلادی، ISO)")
    start_time: time = Field(description="شروع بازه")
    end_time: time | None = Field(default=None, description="پایان بازه")
    kind: VisitSlotKind = Field(
        default=VisitSlotKind.OFFICE_HOUSE, description="حضوری / تلفنی / آنلاین"
    )
    guests: int | None = Field(default=None, ge=1, le=30)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("slot_date")
    @classmethod
    def _not_in_the_past(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("slot_date is in the past")
        return value

    @model_validator(mode="after")
    def _end_after_start(self) -> VisitBookingCreate:
        if self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class VisitBookingResponse(BaseModel):
    """One row of the visit schedule, as the widget renders it."""

    id: uuid.UUID
    property_id: uuid.UUID
    slot_date: date
    start_time: time
    end_time: time | None = None
    status: VisitSlotStatus
    kind: VisitSlotKind
    guests: int | None = None
    notes: str | None = None
    created_at: datetime


class VisitAvailabilityItem(BaseModel):
    """One calendar window on a listing, taken or still free.

    Taken rows expose the *status* but never the visitor: who asked for the
    slot is office business, while the fact it is taken is exactly what the
    prospect needs to pick another hour. ``DRAFT`` holds never appear here at
    all -- they are desk-private by design, and advertising them would leak
    the desk's own planning.
    """

    slot_date: date
    start_time: time
    end_time: time | None = None
    #: False when a DRAFT/REQUESTED/CONFIRMED row already owns the window.
    available: bool
    status: VisitSlotStatus | None = Field(
        default=None, description="None while the window is still free"
    )
    kind: VisitSlotKind | None = Field(
        default=None, description="Echoed from the blocking row, if any"
    )


class VisitAvailabilityResponse(BaseModel):
    """The widget's calendar feed for one listing over a date range."""

    property_id: uuid.UUID
    date_from: date
    date_to: date
    items: list[VisitAvailabilityItem]
    count: int
