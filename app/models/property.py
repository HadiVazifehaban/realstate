"""``Property`` -- the central property/listing entity."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlmodel import SQLModel, Field, Column
from sqlmodel import Relationship as SQLModelRelationship
from sqlalchemy import JSON, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import (
    pg_enum,
    point_column,
    timestamp_column,
    utcnow,
    uuid_column,
)
from app.models.enums import (
    DealType,
    PriceChangeSource,
    PropertySource,
    PropertyStatus,
    PropertyType,
    SubmitterType,
    ValuationStatus,
)

_SourceCol = Column(pg_enum(PropertySource, "property_source"), nullable=False)
_TypeCol = Column(pg_enum(PropertyType, "property_type"), nullable=False)
_DealCol = Column(pg_enum(DealType, "deal_type"), nullable=False)
_StatusCol = Column(pg_enum(PropertyStatus, "property_status"), nullable=False, index=True)
# ``index=True`` cannot be passed alongside ``sa_column`` in a Field(), so the
# bargain radar index is declared on the Column itself (same as ``_StatusCol``).
_ValuationStatusCol = Column(
    pg_enum(ValuationStatus, "valuation_status"), nullable=False, index=True
)


class Property(SQLModel, table=True):
    """A real-estate file / listing stored in the office catalog."""

    __tablename__ = "property"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    code: str = Field(default="", index=True, max_length=64, description="کد داخلی فایل")
    title: str = Field(default="", max_length=255)
    description: str = Field(default="")

    # -- Classification ---------------------------------------------------------
    property_type: PropertyType = Field(default=PropertyType.APARTMENT, sa_column=_TypeCol)
    deal_type: DealType = Field(default=DealType.SALE, sa_column=_DealCol)
    status: PropertyStatus = Field(default=PropertyStatus.ACTIVE, sa_column=_StatusCol)

    # -- Technical specs --------------------------------------------------------
    area: float | None = Field(default=None, description="متراژ (متر مربع)")
    land_area: float | None = Field(default=None, description="متراژ زمین")
    rooms: int | None = Field(default=None, description="تعداد خواب")
    year_built: int | None = Field(default=None, description="سال ساخت")
    floor: int | None = Field(default=None, description="طبقه")
    total_floors: int | None = Field(default=None, description="تعداد کل طبقات")
    units_per_floor: int | None = Field(default=None, description="تعداد واحد در طبقه")
    has_elevator: bool = Field(default=False)
    has_parking: bool = Field(default=False)
    has_storage: bool = Field(default=False, description="انباری")
    has_balcony: bool = Field(default=False)

    # -- Financials -------------------------------------------------------------
    # BIGINT: Toman prices routinely exceed the 2^31-1 ceiling of INTEGER
    # (a mid-range Tehran apartment is ~12,000,000,000 Toman), so a 32-bit
    # column would overflow on the first real listing.
    price_per_meter: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True),
        description="قیمت هر متر",
    )
    total_price: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True), description="قیمت کل"
    )
    deposit_amount: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True),
        description="ودیعه / رهن",
    )
    monthly_rent: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True),
        description="اجاره ماهانه",
    )

    # -- Location ---------------------------------------------------------------
    location: Any = Field(default=None, sa_column=point_column(nullable=True))
    # Scalar mirror of ``location``: the near-duplicate scan and the public
    # projection both filter/sort on lat/lng, which a geometry expression cannot
    # serve through a plain B-tree. ``submit`` always writes all three together.
    latitude: float | None = Field(default=None, index=True, description="عرض جغرافیایی")
    longitude: float | None = Field(default=None, index=True, description="طول جغرافیایی")
    province: str = Field(default="", max_length=64)
    city: str = Field(default="", max_length=64)
    neighborhood: str = Field(default="", max_length=128, index=True)

    # -- Hybrid flags -----------------------------------------------------------
    source: PropertySource = Field(default=PropertySource.MANUAL_OFFICE, sa_column=_SourceCol)
    source_ref: str | None = Field(default=None, max_length=255, description="شناسه آگهی دیوار")
    # Divar autonomous ingestion (Phase 2)
    external_id: str | None = Field(
        default=None,
        index=True,
        unique=True,
        max_length=128,
        description="شناسه یکتای آگهی دیوار (divar_token)",
    )
    content_hash: str | None = Field(
        default=None,
        index=True,
        max_length=128,
        description="SHA256(city+district+area+floor+rounded_price) برای ثبت‌های تکراری",
    )
    raw_data: dict | None = Field(
        default=None,
        sa_column=Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True),
        description="پاسخ خام ویجت‌های دیوار جهت بازپردازش",
    )
    is_shared_to_mls: bool = Field(default=False, index=True)
    storage_node_id: str = Field(default="local", max_length=128)

    # -- Automated valuation (Phase 3b AVM) ------------------------------------
    # ``price_per_meter`` above is the *asked* price; the two fields below are the
    # engine's verdict so a bargain never has to be recomputed per request.
    valuation_status: ValuationStatus = Field(
        default=ValuationStatus.UNKNOWN,
        sa_column=_ValuationStatusCol,
        description="وضعیت ارزش‌گذاری خودکار نسبت به میانه بازار محله",
    )
    valuation_deviation_pct: float | None = Field(
        default=None,
        description="انحراف قیمت از میانه منطقه (درصد؛ منفی = زیر بازار)",
    )
    valuation_median_price_per_meter: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, nullable=True),
        description="میانه قیمت هر متر در پنجره زمانی محاسبه‌شده",
    )
    valuation_sample_count: int | None = Field(
        default=None, description="تعداد نمونه معتبر شرکت‌کننده در محاسبه"
    )
    valuation_updated_at: datetime | None = Field(
        default=None, sa_column=timestamp_column(nullable=True)
    )

    created_by_id: uuid.UUID | None = Field(default=None, foreign_key="agency_user.id")
    # Keycloak subject of the account that filed an internal listing. Scraped
    # rows stay NULL and can never be used to create an internal conversation.
    owner_subject: str | None = Field(default=None, max_length=255, index=True)
    # Set only for direct first-party listings submitted from a validated
    # workspace. Scraped/global inventory remains unscoped (NULL).
    agency_id: uuid.UUID | None = Field(default=None, foreign_key="agency.id", index=True)

    # -- Who filed this listing ------------------------------------------------
    # Independent of ``source`` (the channel) and of ``created_by_id`` (the
    # account): this is the *class of party* that pressed submit. Snapshotted at
    # write time, so a later role change cannot rewrite history -- a listing an
    # owner filed stays PERSON even after the account is promoted to broker.
    # Nullable because a scraped row is not a submission at all, and there
    # "unknown" is honest where a guessed AGENCY would be a fabrication.
    submitter_type: SubmitterType | None = Field(
        default=None,
        sa_column=Column(pg_enum(SubmitterType, "submitter_type"), nullable=True),
        description="نوع ثبت‌کننده در لحظهٔ ثبت — شخص حقیقی یا بنگاه",
    )

    # -- Listed-by (advisor card on the detail page) ---------------------------
    # Business identity of whoever published the listing, never the owner's
    # personal contact -- that lives encrypted in the PII vault. Populated from
    # the crawler's contact block (Delta's ``offeredBy``/``realEstateAgency``,
    # Sheypoor's seller metadata); null for a listing the office registered.
    agent_name: str | None = Field(default=None, max_length=255)
    agency_name: str | None = Field(default=None, max_length=255)
    #: Portal-side identifier of the agency, used to link "other listings by this
    #: agency" once the agency page exists.
    agency_slug: str | None = Field(default=None, max_length=255)

    # -- Visit scheduler --------------------------------------------------------
    # ``ClassVar`` tells pydantic to skip this attribute so it is not treated as
    # a JSON field; the mapper still wires it up. The target class
    # (``PropertyVisitBooking``) lives in a module that imports this one, so the
    # SQLAlchemy relationship is declared here by *name* instead -- an annotated
    # ``ClassVar[...]`` would make the mapper try to resolve that annotation as
    # the target and fail.
    visit_bookings: ClassVar[Any] = SQLModelRelationship(
        sa_relationship=relationship(
            "PropertyVisitBooking", back_populates="property"
        )
    )

    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
