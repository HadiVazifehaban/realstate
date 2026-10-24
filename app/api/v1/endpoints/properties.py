"""First-party property submission, valuation and price-history endpoints.

Property management API endpoints for real estate listings and operations.

**فارسی**: نقاط پایانی API مدیریت املاک و مستغلات برای آگهی‌ها و عملیات مرتبط.

## توضیحات کلی
این ماژول شامل تمامی عملیات مربوط به مدیریت املاک و مستغلات می‌شود:
- ثبت و ویرایش آگهی‌های ملک
- مدیریت رسانه‌ها (تصاویر، ویدیوها)
- ارزش‌گذاری و تحلیل بازار
- رزرو بازدید از ملک
- گزارش‌گیری و تحلیل‌های آماری

## الزامات لایسنس
تمامی routeها تحت محافظ لایسنس تجاری Phase 1 قرار دارند:
- بدون لایسنس ACTIVE/GRACE دفتر نمی‌تواند معامله کند.
- این الزام با endpoints اسکرپر هماهنگ است.

Every route sits behind the Phase 1 commercial license guard, matching the
scraper endpoints: without an ACTIVE/GRACE license the office cannot trade.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, time, timedelta

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.api.deps import LicenseGuard, PrincipalDep, PropertiesAccessDep, SessionDep, SettingsDep
from app.api.v1.endpoints.crm import _resolve_actor_user
from app.core.config import get_settings
from app.core.crypto import PiiCipher
from app.core.identity import IdentityError, submitter_type_for
from app.services import property_media_store
from app.models import (
    Property,
    PropertyMedia,
    PropertyPriceHistory,
    PropertyReport,
    PropertyVisitBooking,
)
from app.models.base import utcnow
from app.models.enums import (
    DealType,
    LEGACY_SOURCE_ALIASES,
    MediaType,
    PriceChangeSource,
    PropertySource,
    PropertyStatus,
    PropertyType,
    SubmitterType,
    ValuationStatus,
    VisitSlotStatus,
)
from app.schemas.properties import (
    BLOCKING_STATUSES,
    BargainListResponse,
    NeighbourhoodMarketResponse,
    NeighbourhoodStat,
    PriceHistoryEntry,
    PriceUpdateRequest,
    PropertyListResponse,
    PropertyMediaItem,
    NearbyPoiResponse,
    PropertyMediaListResponse,
    PropertyReportCreate,
    PropertyReportResponse,
    PropertySubmitRequest,
    PropertySubmitResponse,
    PropertySummary,
    ReverseGeocodeRequest,
    ReverseGeocodeResponse,
    ValuationResponse,
    VisitAvailabilityItem,
    VisitAvailabilityResponse,
    VisitBookingCreate,
    VisitBookingResponse,
    DealSummaryItem,
    DealSummaryResponse,
)
from app.services import geo, market, poi_service, submission, valuation
from app.services.ingestion.deduplicator import canonical_source

router = APIRouter()

#: Canonical source -> every stored spelling that folds onto it. Built by running
#: ``canonical_source`` over all members rather than by inverting
#: ``LEGACY_SOURCE_ALIASES``, because a plain inversion would still need to
#: decide what the legacy members map to *from*, and getting that backwards
#: silently narrows the filter back to a single label.
_SOURCE_EQUIVALENTS: dict[PropertySource, set[PropertySource]] = {}
for _member in PropertySource:
    _SOURCE_EQUIVALENTS.setdefault(canonical_source(_member), set()).add(_member)
del _member


async def _media_by_property(
    session: SessionDep, property_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[PropertyMedia]]:
    """Images for a page of listings, keyed by property.

    One query for the whole page rather than one per row: a 50-row radar feed
    would otherwise issue 50 round trips before the cards could render.
    """
    if not property_ids:
        return {}
    stmt = (
        select(PropertyMedia)
        .where(PropertyMedia.property_id.in_(property_ids))
        .order_by(PropertyMedia.is_cover.desc(), PropertyMedia.sort_order)
    )
    rows = (await session.exec(stmt)).all()
    grouped: dict[uuid.UUID, list[PropertyMedia]] = {}
    for row in rows:
        grouped.setdefault(row.property_id, []).append(row)
    return grouped


def _cover_url(prop: Property, media: Sequence[PropertyMedia] | None) -> tuple[str | None, int]:
    """The servable cover image and the total image count for one listing.

    Two shapes come back: a crawled photo is an absolute ``cloud_url`` straight
    from the portal's CDN, while an advisor's own upload has no cloud URL and is
    served from this node instead -- the relative path the browser resolves
    against its configured API base (``/backend/api/v1`` under the dashboard's
    proxy). ``local_path`` itself never leaves the API: it is a path on the
    office disk, and a browser on the LAN cannot fetch it.
    """
    if not media:
        return None, 0
    images = [m for m in media if m.media_type == MediaType.IMAGE]
    if not images:
        return None, 0
    cover = next((m for m in images if m.is_cover), images[0])
    url = cover.cloud_url or f"/properties/media/file/{cover.id}"
    return url, len(images)


def _summary(
    prop: Property,
    *,
    exact_pin: bool,
    media: Sequence[PropertyMedia] | None = None,
) -> PropertySummary:
    """Project a property for the API without leaking owner PII."""
    latitude, longitude = prop.latitude, prop.longitude
    if not exact_pin and latitude is not None and longitude is not None:
        latitude, longitude = geo.blur_point(latitude, longitude)
    cover_url, images_count = _cover_url(prop, media)
    return PropertySummary(
        id=prop.id,
        title=prop.title,
        property_type=prop.property_type,
        deal_type=prop.deal_type,
        status=prop.status,
        neighborhood=prop.neighborhood,
        city=prop.city,
        area=prop.area,
        rooms=prop.rooms,
        total_price=prop.total_price,
        price_per_meter=prop.price_per_meter,
        valuation_status=prop.valuation_status,
        valuation_deviation_pct=prop.valuation_deviation_pct,
        valuation_median_price_per_meter=prop.valuation_median_price_per_meter,
        valuation_sample_count=prop.valuation_sample_count,
        latitude=latitude,
        longitude=longitude,
        exact_pin=exact_pin,
        # Legacy source values are folded onto their canonical member here, so
        # the card never has to know which spelling a row was written with.
        source=LEGACY_SOURCE_ALIASES.get(prop.source, prop.source),
        # The class of party that filed it, snapshotted at write time. Carried
        # through verbatim -- not derived from `source`, because a broker may
        # file a private owner's unit and the two facts must not collapse.
        submitter_type=prop.submitter_type,
        agent_name=prop.agent_name,
        agency_name=prop.agency_name,
        source_ref=prop.source_ref,
        floor=prop.floor,
        total_floors=prop.total_floors,
        year_built=prop.year_built,
        has_elevator=prop.has_elevator,
        has_parking=prop.has_parking,
        has_storage=prop.has_storage,
        has_balcony=prop.has_balcony,
        deposit_amount=prop.deposit_amount,
        monthly_rent=prop.monthly_rent,
        updated_at=prop.updated_at,
        description=prop.description or "",
        cover_url=cover_url,
        images_count=images_count,
    )


async def _load(session: SessionDep, property_id: uuid.UUID) -> Property:
    prop = await session.get(Property, property_id)
    if prop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail={"error": "property_not_found"}
        )
    return prop


@router.post(
    "/reverse-geocode",
    response_model=ReverseGeocodeResponse,
    summary="Resolve an OSM pin to Persian district names (before submitting) - تبدیل مختصات به نام محل",
)
async def reverse_geocode(
    payload: ReverseGeocodeRequest,
    session: SessionDep,
    settings: SettingsDep,
    _license: LicenseGuard,
) -> ReverseGeocodeResponse:
    """Let the wizard confirm the district before the advisor commits the form.
    
    **فارسی**: تبدیل مختصات جغرافیایی به نام محل، محله و شهر فارسی.
    
    این نقطه پایانی برای تأیید محل دقیق ملک قبل از ثبت نهایی آگهی استفاده می‌شود.
    
    ## Parameters (پارامترها)
    - **latitude** (عرض جغرافیایی): موقعیت شمالی-جنوبی
    - **longitude** (طول جغرافیایی): موقعیت شرقی-غربی
    
    ## Response (پاسخ)
    - **city** (شهر): نام شهر فارسی
    - **district** (منطقه): نام منطقه/منطقه
    - **neighbourhood** (محله): نام محله
    - **postcode** (کد پستی): کد پستی منطقه
    - **formatted_address** (آدرس فرمت شده): آدرس کامل فارسی
    """

    located = await geo.reverse_geocode(session, payload.latitude, payload.longitude, settings)
    return ReverseGeocodeResponse(**located)


@router.post(
    "",
    response_model=PropertySubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a property from a first-party submission (owner/advisor) - ثبت ملک جدید",
)
async def submit_property(
    payload: PropertySubmitRequest,
    session: SessionDep,
    settings: SettingsDep,
    principal: PropertiesAccessDep,
    _license: LicenseGuard,
) -> PropertySubmitResponse:
    """First-class UGC path: an owner/advisor pin outranks a scraped listing.

    **فارسی**: ثبت ملک جدید از طریق ارسال مستقیم مالک یا مشاور.

    مسیر محتوای تولید شده توسط کاربر: یک پین مالک/مشاور از آگهی‌های جمع‌آوری شده اولویت دارد.
    اگر واحد مشابه از قبل در سیستم وجود داشته باشد (تطابق اثر انگشت، یا در فاصله ۵۰ متری با مشخصات مشابه)
    ارسال به‌روزرسانی آن رکورد را انجام می‌دهد به جای ایجاد تکراری -- ``created=false`` به کلاینت می‌گوید که این اتفاق افتاده است.

    ## Features (ویژگی‌ها)
    - **Duplicate detection** (تشخیص تکراری): جلوگیری از ثبت آگهی‌های تکراری
    - **Location verification** (تأیید موقعیت): بررسی موقعیت جغرافیایی
    - **Automatic valuation** (ارزش‌گذاری خودکار): محاسبه ارزش ملک پس از ثبت

    ## Common Property Types (انواع متداول ملک)
    - APARTMENT (آپارتمان), VILLA (ویلا), LAND (زمین)
    - OFFICE (دفتر), SHOP (مغازه), WAREHOUSE (انبار)

    ## Deal Types (انواع معامله)
    - SALE (فروش), RENT (اجاره), PRE_SALE (پیش‌فروش)

    **Who may file, and as what.** The submitter class (شخص حقیقی / بنگاه) is
    derived from the signed token by :func:`submitter_type_for`, never read from
    the body -- there is deliberately no ``submitter_type`` field on
    ``PropertySubmitRequest``. A caller who could name their own class would
    file an office listing as a private owner and inherit the owner's
    provenance ranking (``SOURCE_PRECEDENCE``) plus the "مالک مستقیم" badge.

    Three things stay separate here, because they are three facts:

    * **who filed it** -- ``created_by_id`` (the account) and ``submitter_type``
      (the class of party), both from the principal;
    * **who owns the unit** -- ``owner_name``/``owner_phone``, which go to the
      encrypted vault untouched. A broker filing for a private owner is
      ``AGENCY`` while the contacts in the vault remain the owner's;
    * **which channel it came through** -- ``source``, derived from the class
      above rather than hard-coded, so a genuine owner registration finally
      outranks an office one instead of both landing on one bucket.

    The KYC gate already ran in :func:`app.api.deps.get_principal`, so a pending
    account is refused before the role check -- no role, however senior, reaches
    this handler unapproved.
    """
    try:
        submitter_type = submitter_type_for(principal)
    except IdentityError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.code, "message": exc.message},
        ) from exc

    try:
        result = await submission.submit_property(
            session,
            latitude=payload.latitude,
            longitude=payload.longitude,
            deal_type=payload.deal_type,
            property_type=payload.property_type,
            title=payload.title,
            description=payload.description,
            area=payload.area,
            rooms=payload.rooms,
            floor=payload.floor,
            total_floors=payload.total_floors,
            year_built=payload.year_built,
            total_price=payload.total_price,
            deposit_amount=payload.deposit_amount,
            monthly_rent=payload.monthly_rent,
            has_elevator=payload.has_elevator,
            has_parking=payload.has_parking,
            has_storage=payload.has_storage,
            has_balcony=payload.has_balcony,
            owner_name=payload.owner_name,
            owner_phone=payload.owner_phone,
            settings=settings,
            cipher=PiiCipher.from_key_file(settings.resolve_path(settings.pii_key_file)),
            created_by_id=await _resolve_actor_user(session, principal),
            submitter_type=submitter_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_submission", "message": str(exc)},
        ) from exc

    return PropertySubmitResponse(
        property_id=result.property_id,
        created=result.created,
        district=result.district,
        valuation_status=result.valuation_status,
    )


@router.get(
    "",
    response_model=PropertyListResponse,
    summary="list (لیست) the node's live inventory (crawled + first-party, newest first) - لیست املاک",
)
async def list_properties(
    session: SessionDep,
    _principal: PropertiesAccessDep,
    q: str | None = Query(default=None, description="متن آزاد روی عنوان/محله"),
    # Repeated on purpose: the city filter is multi-select (an advisor's market
    # is the capital *and* its satellites), and the province chips expand to
    # every county in the province rather than making the browser pick.
    city: list[str] | None = Query(default=None),
    neighborhood: str | None = Query(default=None),
    # Repeated on purpose, exactly like `property_type` below. "رهن و اجاره"
    # is one choice in the desk's own vocabulary but two stored deal types --
    # RENT and FULL_MORTGAGE -- so a single-value filter would make picking the
    # lease family silently drop every deposit-only listing from the feed.
    deal_type: list[DealType] | None = Query(default=None),
    # Repeated on purpose: the showcase filter's category tabs map to several
    # types at once (مسکونی -> APARTMENT + SUITE + PENTHOUSE), and sending one
    # request per type would page three times for one row set.
    property_type: list[PropertyType] | None = Query(default=None),
    status_filter: PropertyStatus | None = Query(default=None, alias="status"),
    valuation_status: ValuationStatus | None = Query(default=None),
    source: PropertySource | None = Query(default=None),
    # Inclusive range filters for the showcase toolbar, which filters the whole
    # page rather than only the rails. Prices are read off the column that
    # belongs to the deal -- total for a sale, deposit (falling back to monthly
    # rent) for a lease -- so one slider bounds both sides of the inventory the
    # way the client-side showcase filter already does.
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    min_area: int | None = Query(default=None, ge=0),
    max_area: int | None = Query(default=None, ge=0),
    # -- Building & unit attributes -----------------------------------------
    # Everything below reads a column the node already stores on every row
    # (see ``Property``), so the showcase filter can advertise a box that
    # actually narrows the feed rather than one the endpoint ignores.
    min_rooms: int | None = Query(default=None, ge=0),
    max_rooms: int | None = Query(default=None, ge=0),
    min_land_area: int | None = Query(default=None, ge=0),
    max_land_area: int | None = Query(default=None, ge=0),
    min_year_built: int | None = Query(default=None, ge=1200),
    max_year_built: int | None = Query(default=None, ge=1200),
    min_floor: int | None = Query(default=None, ge=0),
    max_floor: int | None = Query(default=None, ge=0),
    # Amenity switches: `true` means "must have it". The node stores one bool
    # per amenity and no parking *kind*, so a dedicated/shared split is not
    # something this filter can promise.
    has_parking: bool | None = Query(default=None),
    has_elevator: bool | None = Query(default=None),
    has_storage: bool | None = Query(default=None),
    has_balcony: bool | None = Query(default=None),
    # -- Financial, on the unit price rather than the total -----------------
    # Price per square metre falls back to total/area, so a scraped row whose
    # `price_per_meter` was never populated still filters instead of silently
    # dropping out of the range.
    min_price_per_meter: int | None = Query(default=None, ge=0),
    max_price_per_meter: int | None = Query(default=None, ge=0),
    # -- Shekarchi bargain radar -------------------------------------------
    # How far below the neighbourhood AVM a listing has to sit, in percent.
    # `valuation_deviation_pct` is negative for under-priced, so a 10 here
    # asks for rows at least 10% under market.
    below_market_pct: int | None = Query(default=None, ge=0, le=90),
    # Who filed it: PERSON is the owner-direct route, AGENCY the desk's own.
    submitter_type: SubmitterType | None = Query(default=None),
    # -- Recency ------------------------------------------------------------
    # Hours since `created_at`. A new file on a hot street is the one thing a
    # working advisor needs before anyone else, and it is the only way to sort
    # a 6k-row book by "what landed today".
    published_within_hours: int | None = Query(default=None, ge=1, le=8760),
    # Raised from 200 so the lead picker can walk the whole node in one pass.
    # The radar and price-history endpoints below keep the tighter cap -- they
    # are dashboards, not pickers, and a 2000-row dashboard is useless anyway.
    limit: int = Query(default=60, ge=1, le=2500),
    offset: int = Query(default=0, ge=0)
) -> PropertyListResponse:
    """The full feed behind ``/dashboard/properties``.
    
    **فارسی**: لیست کامل املاک موجود در سیستم (جمع‌آوری شده + ارسال مستقیم، جدیدترین اول).
    
    Deliberately **not** valuation-gated: an advisor has to see inventory the
    moment it lands, even before the engine has enough comparables to publish
    a verdict (which is why the radar alone can look empty on a fresh node).
    
    ## فید کامل پشت ``/dashboard/properties``
    
    عمداً **بدون دروازه ارزش‌گذاری**: یک مشاور باید موجودی را در لحظه ورود ببیند،
    حتی قبل از اینکه موتور مقایسه‌های کافی برای انتشار رأی داشته باشد
    (به همین دلیل است که رادار به تنهایی ممکن است در یک نود تازه خالی به نظر برسد).
    
    ## ویژگی‌های فیلترینگ
    - جستجوی متن آزاد در عنوان و محله
    - فیلتر چند انتخابی شهرها
    - محدوده قیمت و متراژ
    - ویژگی‌های واحد (تعداد اتاق، طبقه، سال ساخت)
    - امکانات (پارکینگ، آسانسور، انباری، بالکن)
    - رادار معامله مناسب (درصد زیر قیمت بازار)
    - نوع ثبت‌کننده (مالک مستقیم، آژانس)
    - فیلتر زمانی (ساعات از زمان ایجاد)
    
    ## انواع فیلترهای پشتیبانی شده
    1. **جغرافیایی**: شهر، محله
    2. **مالی**: قیمت، قیمت هر متر
    3. **فیزیکی**: متراژ، تعداد اتاق، طبقه
    4. **زمانی**: ساعت از زمان انتشار
    5. **وضعیت**: نوع ملک، نوع معامله، وضعیت ارزش‌گذاری
    """
    conditions = []
    # Anonymous visitors may see only currently active public inventory. The
    # caller cannot broaden this to drafts, withdrawn, sold, or archived rows.
    if _principal is None:
        conditions.append(Property.status == PropertyStatus.ACTIVE)
    if q:
        like = f"%{q.strip()}%"
        conditions.append(or_(Property.title.ilike(like), Property.neighborhood.ilike(like)))
    if city:
        # A list, because the feed's city filter is multi-select. An empty
        # selection is the same as none at all: «همهٔ شهرها», not «هیچ شهر».
        conditions.append(Property.city.in_(city))
    if neighborhood:
        conditions.append(Property.neighborhood == neighborhood)
    if deal_type:
        # Every stored spelling of the picked families, not just the canonical
        # ones. `in_` rather than `==` so a lease ask covers RENT and
        # FULL_MORTGAGE in one request instead of paging twice for one row set.
        conditions.append(Property.deal_type.in_(deal_type))
    if property_type:
        conditions.append(Property.property_type.in_(property_type))
    if status_filter is not None:
        conditions.append(Property.status == status_filter)
    if valuation_status is not None:
        conditions.append(Property.valuation_status == valuation_status)
    if source is not None:
        # Match every stored spelling of this source, not just the canonical
        # one. Rows scraped before the rename still carry DIVAR_KENAR /
        # DIVAR_SCRAPER, so filtering on `source == DIVAR` alone would show an
        # empty feed on a node whose cards are all labelled "دیوار".
        wanted = canonical_source(source)
        equivalents = _SOURCE_EQUIVALENTS.get(wanted) or {wanted}
        conditions.append(Property.source.in_(equivalents))
    if min_price is not None or max_price is not None:
        # The deal-appropriate price column, evaluated per row: a sales total
        # against a lease deposit would compare two different things.
        price_expr = case(
            (Property.deal_type == DealType.SALE, Property.total_price),
            else_=func.coalesce(Property.deposit_amount, Property.monthly_rent)
        )
        if min_price is not None:
            conditions.append(price_expr >= min_price)
        if max_price is not None:
            conditions.append(price_expr <= max_price)
    if min_area is not None:
        conditions.append(Property.area >= min_area)
    if max_area is not None:
        conditions.append(Property.area <= max_area)

    # -- Building & unit attributes -----------------------------------------
    if min_rooms is not None:
        conditions.append(Property.rooms >= min_rooms)
    if max_rooms is not None:
        # `4+` is an open range, so the client sends no upper bound for it and
        # `max_rooms` stays unset rather than guessing a ceiling.
        conditions.append(Property.rooms <= max_rooms)
    if min_land_area is not None:
        conditions.append(Property.land_area >= min_land_area)
    if max_land_area is not None:
        # A listing without a land figure is an apartment with nothing outside
        # it, not one whose plot is missing from the record. Rows with a NULL
        # land area would fail every `>=` bound, so they are only excluded when
        # the advisor actually asked for a yard.
        conditions.append(
            or_(Property.land_area.is_(None), Property.land_area <= max_land_area)
        )
    if min_year_built is not None:
        conditions.append(Property.year_built >= min_year_built)
    if max_year_built is not None:
        # Same reasoning: an unknown build year must not read as "old".
        conditions.append(
            or_(Property.year_built.is_(None), Property.year_built <= max_year_built)
        )
    if min_floor is not None:
        conditions.append(Property.floor >= min_floor)
    if max_floor is not None:
        conditions.append(
            or_(Property.floor.is_(None), Property.floor <= max_floor)
        )
    if has_parking:
        conditions.append(Property.has_parking.is_(True))
    if has_elevator:
        conditions.append(Property.has_elevator.is_(True))
    if has_storage:
        conditions.append(Property.has_storage.is_(True))
    if has_balcony:
        conditions.append(Property.has_balcony.is_(True))

    if min_price_per_meter is not None or max_price_per_meter is not None:
        # `price_per_meter` is a stored column that the scrapers leave null on a
        # good share of rows; computing it from the total keeps those listings
        # inside the range instead of silently dropping every un-priced square
        # metre in the book.
        ppm_expr = func.coalesce(
            Property.price_per_meter,
            Property.total_price / func.nullif(Property.area, 0)
        )
        if min_price_per_meter is not None:
            conditions.append(ppm_expr >= min_price_per_meter)
        if max_price_per_meter is not None:
            conditions.append(ppm_expr <= max_price_per_meter)

    # -- Shekarchi bargain radar -------------------------------------------
    if below_market_pct is not None:
        # Deviation is signed: -12 means "12% under the neighbourhood median".
        # Rows with no verdict yet are excluded on purpose -- a listing the
        # engine has not judged is not a bargain, it is unpriced.
        conditions.append(
            Property.valuation_deviation_pct <= -below_market_pct
        )
    if submitter_type is not None:
        conditions.append(Property.submitter_type == submitter_type)

    if published_within_hours is not None:
        cutoff = utcnow() - timedelta(hours=published_within_hours)
        conditions.append(Property.created_at >= cutoff)

    count_stmt = select(func.count()).select_from(Property)
    rows_stmt = select(Property)
    for condition in conditions:
        count_stmt = count_stmt.where(condition)
        rows_stmt = rows_stmt.where(condition)

    total = int((await session.exec(count_stmt)).one() or 0)
    rows = (
        await session.exec(
            rows_stmt.order_by(Property.created_at.desc()).offset(offset).limit(limit)
        )
    ).all()
    media_by_property = await _media_by_property(session, [row.id for row in rows])
    items = [
        _summary(row, exact_pin=_principal is not None, media=media_by_property.get(row.id))
        for row in rows
    ]
    return PropertyListResponse(count=total, items=items, limit=limit, offset=offset)


@router.get(
    "/cities",
    summary="Distinct cities present in the node's inventory (فهرست شهرهای دفتر)",
)
async def inventory_cities(
    session: SessionDep,
    _principal: PropertiesAccessDep | None = None,
) -> dict[str, list[str]]:
    """The cities this node actually holds, straight from the listings table.
    
    **فارسی**: شهرهای موجود در دیتابیس نود، مستقیماً از جدول آگهی‌ها.
    
    The showcase filter's primary source is the node's own GIS gateway, but
    that list can be unreachable when Nominatim or the Iran Locations container
    is down -- which used to leave the city dropdown silently empty on an office
    LAN install. Cities read off the inventory are always filterable by definition: 
    the radar's ``city`` parameter is an exact match on ``Property.city``, so offering only
    spellings the crawler has actually written can never produce an empty feed.
    
    ## توضیحات
    منبع اصلی فیلتر showcase، دروازه GIS نود است، اما
    آن لیست ممکن است زمانی که Nominatim یا کانتینر Iran Locations
    پایین است، غیرقابل دسترس باشد -- که قبلاً باعث می‌شد dropdown شهر
    در نصب LAN دفتر خالی بماند. شهرهای خوانده شده از موجودی همیشه
    قابل فیلتر هستند: پارامتر ``city`` رادار یک تطابق دقیق روی ``Property.city`` است،
    بنابراین ارائه فقط املاهایی که کراولر واقعاً نوشته است هرگز نمی‌تواند یک فید خالی تولید کند.
    
    ## Response (پاسخ)
    - **cities**: لیست شهرهای منحصربه‌فرد موجود در دیتابیس
    """
    conditions = [Property.city.is_not(None), Property.city != ""]
    if _principal is None:
        conditions.append(Property.status == PropertyStatus.ACTIVE)
    rows = (
        await session.exec(
            select(Property.city)
            .where(*conditions)
            .distinct()
            .order_by(Property.city)
        )
    ).all()
    return {"cities": [city for city in rows if city]}


@router.get(
    "/bargains",
    response_model=BargainListResponse,
    summary="Listings priced below the local market (agent radar feed) - لیست معاملات مناسب",
)
async def list_bargains(
    session: SessionDep,
    settings: SettingsDep,
    neighborhood: str | None = Query(default=None, description="نام محله (اختیاری)"),
    city: str | None = Query(default=None, description="نام شهر (اختیاری)"),
    limit: int = Query(default=50, ge=1, le=200, description="تعداد رکوردهای برگشتی"),
) -> BargainListResponse:
    """Listings priced below the local market (agent radar feed)
    
    **فارسی**: آگهی‌هایی که زیر قیمت بازار محلی قیمت‌گذاری شده‌اند (فید رادار مشاور).
    
    ## توضیحات
    این نقطه پایانی آگهی‌هایی را برمی‌گرداند که نسبت به ارزش‌گذاری بازار محلی
    قیمت پایین‌تری دارند (فرصت‌های معاملاتی مناسب).
    
    ## پیش‌نیازها
    - **VALUATION_ENABLED**: باید true باشد
    - **لایسنس فعال**: نیاز به لایسنس تجاری Phase 1
    
    ## پارامترهای فیلتر
    - **neighborhood** (محله): فیلتر بر اساس محله خاص
    - **city** (شهر): فیلتر بر اساس شهر خاص
    - **limit** (محدودیت): تعداد رکوردهای برگشتی (1-200)
    
    ## معیارهای انتخاب
    - وضعیت ارزش‌گذاری: VALIDATED
    - درصد انحراف قیمت: منفی (زیر قیمت بازار)
    - آگهی‌های فعال (ACTIVE status)
    """
    if not settings.valuation_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "valuation_disabled",
                "message": "Set VALUATION_ENABLED=true to use the bargain radar.",
            },
        )
    rows = await valuation.find_bargains(
        session, neighbourhood=neighborhood, city=city, limit=limit
    )
    # Office staff work from this node's own book, so the exact pin is shown;
    # the public portal keeps using the masked projection.
    media_by_property = await _media_by_property(session, [row.id for row in rows])
    items = [
        _summary(row, exact_pin=True, media=media_by_property.get(row.id))
        for row in rows
    ]
    return BargainListResponse(count=len(items), items=items)


@router.get(
    "/market/neighbourhoods",
    response_model=NeighbourhoodMarketResponse,
    summary="Per-neighbourhood medians for the market map - فارسی",
)
async def neighbourhood_market(
    session: SessionDep,
    city: str | None = Query(default=None),
    deal_type: list[DealType] | None = Query(default=None),
    min_files: int = Query(default=1, ge=1, le=50),
    limit: int = Query(default=200, ge=1, le=500),
) -> NeighbourhoodMarketResponse:
    """The office's own inventory, aggregated by neighbourhood.

    Registered *before* the ``/{property_id}`` routes on purpose: those would
    otherwise claim ``market`` as a property id and answer 422.

    Median price per square metre, not a mean: portal asking prices carry enough
    outliers that a mean neighbourhood is a neighbourhood nobody can buy in.
    """
    overview = await market.neighbourhood_market(
        session,
        city=city,
        deal_types=deal_type,
        min_files=min_files,
        limit=limit,
    )
    return NeighbourhoodMarketResponse(
        city=overview.city,
        deal_types=overview.deal_types,
        count=len(overview.neighbourhoods),
        total_files=overview.total_files,
        priced_files=overview.priced_files,
        median_price_per_meter=overview.median_price_per_meter,
        items=[
            NeighbourhoodStat(
                neighborhood=stat.neighborhood,
                city=stat.city,
                files=stat.files,
                all_files=stat.all_files,
                median_price_per_meter=stat.median_price_per_meter,
                median_total_price=stat.median_total_price,
                median_deposit=stat.median_deposit,
                median_monthly_rent=stat.median_monthly_rent,
                median_area=stat.median_area,
                bargain_share=stat.bargain_share,
                median_deviation_pct=stat.median_deviation_pct,
                latitude=stat.latitude,
                longitude=stat.longitude,
            )
            for stat in overview.neighbourhoods
        ],
    )


@router.post(
    "/{property_id}/value",
    response_model=ValuationResponse,
    summary="Recompute the automated valuation for one property - فارسی",
)
async def value_property(
    property_id: uuid.UUID,
    session: SessionDep,
    settings: SettingsDep,
    _license: LicenseGuard,
) -> ValuationResponse:
    if not settings.valuation_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "valuation_disabled", "message": "Set VALUATION_ENABLED=true."},
        )
    prop = await _load(session, property_id)
    result = await valuation.value_property(session, prop)
    return ValuationResponse(
        property_id=prop.id,
        valuation_status=result.status,
        deviation_pct=result.deviation_pct,
        median_price_per_meter=result.median_price_per_meter,
        sample_count=result.sample_count,
        bargain=result.is_bargain,
        explain=result.explain,
    )


@router.post(
    "/{property_id}/price",
    response_model=PropertySummary,
    summary="Record an advisor price edit (always appended to the timeline) - فارسی",
)
async def update_price(
    property_id: uuid.UUID,
    payload: PriceUpdateRequest,
    session: SessionDep,
    settings: SettingsDep,
    _license: LicenseGuard,
) -> PropertySummary:
    prop = await _load(session, property_id)
    entry = await submission.record_price(
        session, prop, new_price=payload.new_price, source=PriceChangeSource.MANUAL,
        source_ref=payload.reason or None,
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "price_unchanged", "message": "قیمت تغییری نکرده است."},
        )
    await session.commit()
    await session.refresh(prop)

    # A price move changes the bargain verdict, so re-value immediately.
    if settings.valuation_enabled:
        await valuation.value_property(session, prop)
    return _summary(prop, exact_pin=True)


@router.post(
    "/{property_id}/media",
    response_model=PropertyMediaListResponse,
    summary="Attach photos and videos to a listing (multipart) - لیست",
)
async def upload_property_media(
    property_id: uuid.UUID,
    session: SessionDep,
    principal: PropertiesAccessDep,
    _license: LicenseGuard,
    files: list[UploadFile] = File(..., description="عکس یا ویدیوی ملک"),
) -> PropertyMediaListResponse:
    """Store the advisor's files and append them to the listing's gallery.

    ``multipart/form-data`` with one or more files. The order of the request is
    the order of the gallery, the first photo of a listing with no cover yet
    becomes the cover, and the response is the full media list so the form can
    show the result of what it just uploaded without a second request.

    Refusals are the point of the guard rails, not accidents: a format the
    browser cannot render, a file over the per-type ceiling, or more than
    ``MAX_FILES_PER_REQUEST`` in one go.
    """
    await _load(session, property_id)
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "no_files", "message": "هیچ فایلی ارسال نشد است."},
        )
    if len(files) > property_media_store.MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error": "too_many_files",
                "message": (
                    f"حداکثر {property_media_store.MAX_FILES_PER_REQUEST} فایل در هر درخواست. "
                    "بقیه را در یک درخواست دیگر بفرستید."
                ),
            },
        )

    existing = (
        await session.exec(
            select(PropertyMedia)
            .where(PropertyMedia.property_id == property_id)
            .order_by(PropertyMedia.sort_order)
        )
    ).all()
    next_order = max((row.sort_order for row in existing), default=-1) + 1
    has_cover = any(row.is_cover for row in existing)

    added: list[PropertyMedia] = []
    for index, upload in enumerate(files):
        content = await upload.read()
        try:
            media_type, extension = property_media_store.classify(upload.content_type or "")
        except property_media_store.UnsupportedMediaError as exc:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail={"error": "unsupported_media_type", "message": str(exc)},
            ) from exc

        ceiling = property_media_store.max_bytes_for(media_type)
        if len(content) > ceiling:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "error": "file_too_large",
                    "message": (
                        f"حجم این فایل بیشتر از حد مجاز است "
                        f"({ceiling // (1024 * 1024)} مگابایت)."
                    ),
                },
            )

        path, _stored = property_media_store.store(property_id, content, extension)
        is_first_cover = media_type == "IMAGE" and not has_cover and index == 0
        added.append(
            PropertyMedia(
                property_id=property_id,
                media_type=MediaType(media_type),
                # Deliberately NULL: this file is on this node, not in the cloud,
                # and the routes below serve it from here.
                cloud_url=None,
                local_path=str(path),
                is_cover=is_first_cover,
                sort_order=next_order + index,
                original_filename=(upload.filename or "")[:255] or None,
                mime_type=upload.content_type,
                size_bytes=len(content)
            )
        )
        if is_first_cover:
            has_cover = True

    session.add_all(added)
    await session.commit()
    return await _media_list(session, property_id)


@router.get(
    "/media/file/{media_id}",
    summary="Stream one stored photo or video back to the browser - فارسی",
)
async def read_property_media(
    media_id: uuid.UUID,
    session: SessionDep,
    _license: LicenseGuard,
) -> FileResponse:
    """The bytes behind a row uploaded through this node's own form.

    Crawled photos are never served from here -- they live on the portal's CDN
    and the gallery links straight to them. A row whose file has since been
    removed from disk answers 404 rather than an empty body, so the gallery can
    tell "gone" from "still loading".

    ``Content-Disposition`` is ``inline``: these are gallery assets a browser
    should render, not attachments to download.
    """
    row = await session.get(PropertyMedia, media_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "media_not_found", "message": "فایل پیدا نشد."},
        )
    path = property_media_store.resolve_stored(row.local_path)
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "media_missing", "message": "فایل روی این نود موجود نیست."},
        )
    return FileResponse(
        path,
        media_type=row.mime_type or "application/octet-stream",
        filename=row.original_filename,
        content_disposition_type="inline"
    )


@router.get(
    "/{property_id}/media",
    response_model=PropertyMediaListResponse,
    summary="Full image gallery for one listing (cover first) - لیست",
)
async def list_property_media(
    property_id: uuid.UUID,
    session: SessionDep,
    _license: LicenseGuard,
) -> PropertyMediaListResponse:
    """Every servable image of a listing.

    Two provenances, one list: a crawled photo is an absolute CDN URL in
    ``cloud_url``, while an advisor's own upload is served back by this node's
    ``/media/file`` route. Rows with neither -- a crawled photo whose URL was
    dropped, or an upload whose file is gone from disk -- are skipped rather
    than returned as a broken ``<img>``.
    """
    await _load(session, property_id)
    return await _media_list(session, property_id)


async def _media_list(session: SessionDep, property_id: uuid.UUID) -> PropertyMediaListResponse:
    """The gallery of one listing, cover first, both provenances."""
    rows = (
        await session.exec(
            select(PropertyMedia)
            .where(PropertyMedia.property_id == property_id)
            .order_by(PropertyMedia.is_cover.desc(), PropertyMedia.sort_order)
        )
    ).all()
    items: list[PropertyMediaItem] = []
    for row in rows:
        if row.cloud_url:
            url: str | None = row.cloud_url
        elif property_media_store.resolve_stored(row.local_path) is not None:
            # Served by this node; the browser resolves the path against the
            # dashboard's API prefix, exactly like a fetched JSON response.
            url = f"/properties/media/file/{row.id}"
        else:
            url = None
        if url:
            items.append(
                PropertyMediaItem(
                    id=row.id,
                    url=url,
                    is_cover=row.is_cover,
                    media_type=row.media_type,
                    sort_order=row.sort_order,
                )
            )
    return PropertyMediaListResponse(property_id=property_id, items=items, count=len(items))


@router.get(
    "/{property_id}/nearby-poi",
    response_model=NearbyPoiResponse,
    summary="Named amenities near a listing (Overpass, cached per block) - لیست",
)
async def nearby_poi(
    property_id: uuid.UUID,
    session: SessionDep,
    settings: SettingsDep,
    _license: LicenseGuard,
    radius_m: int = Query(
        default=None, ge=100, le=2000, description="Metres; defaults to settings"
    ),
) -> NearbyPoiResponse:
    """Bucketed POIs around a listing's pin, nearest first.

    Served from the ``poi_cache`` grid wherever possible. A listing with no
    coordinates returns empty buckets rather than a 404: the page still renders,
    it just has no "amenities nearby" block, which is the honest answer for a pin
    we do not have.
    """
    prop = await _load(session, property_id)
    empty = {key: [] for key in poi_service.BUCKETS}
    if prop.latitude is None or prop.longitude is None:
        return NearbyPoiResponse(property_id=property_id, radius_m=0, buckets=empty)

    radius = radius_m or settings.poi_radius_m
    buckets = await poi_service.nearby_poi(
        session,
        prop.latitude,
        prop.longitude,
        radius_m=radius,
        settings=settings,
    )
    return NearbyPoiResponse(
        property_id=property_id,
        radius_m=radius,
        buckets={key: buckets.get(key, []) for key in poi_service.BUCKETS},
    )


@router.post(
    "/{property_id}/report",
    response_model=PropertyReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Report a listing as inaccurate or abusive - لیست",
)
async def report_property(
    property_id: uuid.UUID,
    payload: PropertyReportCreate,
    session: SessionDep,
    _license: LicenseGuard,
) -> PropertyReportResponse:
    """Record one abuse/accuracy report against a listing."""
    await _load(session, property_id)
    report = PropertyReport(
        property_id=property_id,
        reason=payload.reason,
        detail=payload.detail,
        reporter_email=payload.reporter_email,
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)
    logger.info(
        "listing reported: property=%s reason=%s", property_id, payload.reason
    )
    return PropertyReportResponse(id=report.id, reason=report.reason)


@router.get(
    "/{property_id}/price-history",
    response_model=list[PriceHistoryEntry],
    summary="Price timeline for a property (newest first) - فارسی",
)
async def price_history(
    property_id: uuid.UUID,
    session: SessionDep,
    _license: LicenseGuard,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PriceHistoryEntry]:
    prop = await _load(session, property_id)
    rows = (
        await session.exec(
            select(PropertyPriceHistory)
            .where(PropertyPriceHistory.property_id == property_id)
            .order_by(PropertyPriceHistory.recorded_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        PriceHistoryEntry(
            id=row.id,
            previous_price=row.previous_price,
            new_price=row.new_price,
            price_difference=row.price_difference,
            change_percentage=row.change_percentage,
            source=row.source,
            source_ref=row.source_ref,
            recorded_at=row.recorded_at,
        )
        for row in rows
    ]


@router.get(
    "/{property_id}/visit-slots",
    response_model=VisitAvailabilityResponse,
    summary="Calendar windows of a listing, taken or still free - لیست",
)
async def visit_availability(
    property_id: uuid.UUID,
    session: SessionDep,
    _license: LicenseGuard,
    date_from: date | None = Query(
        default=None, description="اول بازه (ISO)؛ پیش‌فرض امروز"
    ),
    date_to: date | None = Query(
        default=None, description="پایان بازه (ISO)؛ پیش‌فرض ۷ روز بعد"
    ),
) -> VisitAvailabilityResponse:
    """What the visit scheduler can offer on one listing.

    Reads the ``property_visit_booking`` rows in the window and projects every
    *free* candidate window inside the desk's visit hours (09:00-18:00, one
    hour each) plus the taken ones. ``DRAFT`` holds are skipped entirely:
    they are desk-private by design, and listing them would publish the
    desk's own planning to whoever asks.

    Friday (the Iranian weekend) is skipped: the office takes no visits then,
    so offering a Friday slot would only manufacture a request the desk has
    to refuse.
    """
    await _load(session, property_id)
    today = date.today()
    start = date_from or today
    end = date_to or min(start + timedelta(days=6), today + timedelta(days=62))
    if end < start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_range", "message": "پایان بازه قبل از شروع است."},
        )
    if (end - start).days > 62:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "range_too_wide",
                "message": "بازه حداکثر ۶۲ روز (دو ماه شمسی) است.",
            },
        )

    rows = (
        await session.exec(
            select(PropertyVisitBooking)
            .where(
                PropertyVisitBooking.property_id == property_id,
                PropertyVisitBooking.slot_date >= start,
                PropertyVisitBooking.slot_date <= end,
            )
            .order_by(PropertyVisitBooking.slot_date, PropertyVisitBooking.start_time)
        )
    ).all()
    # One blocking row per window: the unique slot constraint guarantees there
    # is at most one, but two *different* statuses can still share a window --
    # a cancelled meeting and its replacement do (that's the point), and then
    # only the blocking one decides the window.
    taken: dict[tuple[date, time], PropertyVisitBooking] = {}
    for row in rows:
        if row.status in BLOCKING_STATUSES:
            taken.setdefault((row.slot_date, row.start_time), row)

    items: list[VisitAvailabilityItem] = []
    day = start
    while day <= end:
        if day.weekday() != 4:  # 4 = Friday
            for hour in range(9, 18):
                start_time = time(hour, 0)
                end_time = time(hour + 1, 0)
                blocking = taken.get((day, start_time))
                if blocking is None:
                    items.append(
                        VisitAvailabilityItem(
                            slot_date=day,
                            start_time=start_time,
                            end_time=end_time,
                            available=True,
                        )
                    )
                elif blocking.status is not VisitSlotStatus.DRAFT:
                    items.append(
                        VisitAvailabilityItem(
                            slot_date=day,
                            start_time=start_time,
                            end_time=blocking.end_time or end_time,
                            available=False,
                            status=blocking.status,
                            kind=blocking.kind,
                        )
                    )
        day += timedelta(days=1)

    return VisitAvailabilityResponse(
        property_id=property_id,
        date_from=start,
        date_to=end,
        items=items,
        count=len(items),
    )


@router.post(
    "/{property_id}/visit-slots",
    response_model=VisitBookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request one viewing window on a listing - لیست",
)
async def book_visit_slot(
    property_id: uuid.UUID,
    payload: VisitBookingCreate,
    session: SessionDep,
    principal: PrincipalDep,
    _license: LicenseGuard,
) -> VisitBookingResponse:
    """File one visit request; the desk confirms it on the CRM board.

    The row always lands as ``REQUESTED`` -- a public request never confirms
    itself. A cheap SELECT runs first so the common double-click gets the
    Persian message; the unique slot constraint is the real arbiter, so the
    ``IntegrityError`` path answers 409 as well and two visitors racing for
    the same hour is normal traffic, not a 500.
    """
    await _load(session, property_id)
    held = (
        await session.exec(
            select(PropertyVisitBooking).where(
                PropertyVisitBooking.property_id == property_id,
                PropertyVisitBooking.slot_date == payload.slot_date,
                PropertyVisitBooking.start_time == payload.start_time,
                PropertyVisitBooking.status.in_(BLOCKING_STATUSES),
            )
        )
    ).first()
    if held is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "slot_taken",
                "message": "این ساعت قبلاً رزرو شده است؛ ساعت دیگری انتخاب کنید.",
            },
        )

    booking = PropertyVisitBooking(
        property_id=property_id,
        created_by_user_id=await _resolve_actor_user(session, principal),
        slot_date=payload.slot_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        kind=payload.kind,
        status=VisitSlotStatus.REQUESTED,
        guests=payload.guests,
        notes=payload.notes,
    )
    session.add(booking)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "slot_taken",
                "message": "این ساعت قبلاً رزرو شده است؛ ساعت دیگری انتخاب کنید.",
            },
        ) from exc
    await session.refresh(booking)
    return VisitBookingResponse(
        id=booking.id,
        property_id=booking.property_id,
        slot_date=booking.slot_date,
        start_time=booking.start_time,
        end_time=booking.end_time,
        status=booking.status,
        kind=booking.kind,
        guests=booking.guests,
        notes=booking.notes,
        created_at=booking.created_at,
    )


@router.get(
    "/{property_id}",
    response_model=PropertySummary,
    summary="Fetch one property (exact pin visible inside the office node) - فارسی",
)
async def get_property(
    property_id: uuid.UUID,
    session: SessionDep,
    _license: LicenseGuard,
) -> PropertySummary:
    prop = await _load(session, property_id)
    # Media is loaded here so `cover_url` and `images_count` describe the same
    # listing the detail page is about. Without it this route reported zero images
    # for every property, including ones with a full gallery, which made the
    # response disagree with the sibling `/media` route for the same id.
    media = await _media_by_property(session, [prop.id])
    return _summary(prop, exact_pin=True, media=media.get(prop.id, []))
@router.get(
    "/deal-summary",
    response_model=DealSummaryResponse,
    summary="Deal-type summary for the overview: purchase (SALE) vs. rental (RENT) counts and values - فارسی",
)
async def deal_summary_route(
    session: SessionDep,
    _license: LicenseGuard,
) -> DealSummaryResponse:
    rows = (
        await session.exec(
            select(
                Property.deal_type,
                func.count(Property.id),
                func.sum(
                    case(
                        (Property.deal_type == DealType.SALE, Property.total_price),
                        else_=func.coalesce(Property.deposit_amount, Property.monthly_rent),
                    )
                ),
            )
            .group_by(Property.deal_type)
        )
    ).all()

    deals: list[DealSummaryItem] = []
    for deal_type, count, value in rows:
        deal_value = int(value) if value is not None else 0
        deals.append(DealSummaryItem(deal_type=deal_type, count=int(count), value=deal_value))

    return DealSummaryResponse(deals=deals)
