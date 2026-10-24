"""Phase 3 matching endpoints: demand ledger + suggestion queue.

**فارسی**: نقاط پایانی تطبیق Phase 3: دفترچه تقاضا + صف پیشنهادات.

All routes sit behind the same commercial license guard as the scraper
(``verify_license_active``): matching is a paid feature of the node.

## توضیحات کلی
این ماژول شامل سیستم تطبیق هوشمند املاک است که:
1. **دفترچه تقاضا (Demands)**: مدیریت نیازهای خریداران و مستأجران
2. **صف پیشنهادات (Matches)**: پیشنهادات تطبیق‌شده بر اساس الگوریتم امتیازدهی

## ویژگی‌های سیستم تطبیق
- تطبیق خودکار املاک با نیازهای مشتریان
- امتیازدهی هوشمند بر اساس معیارهای مختلف
- مدیریت وضعیت پیشنهادات توسط مشاوران
- قابلیت بازسازی امتیازها پس از تغییر معیارها
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import LicenseGuard, SessionDep
from app.models import ClientDemand, Property, PropertyMatch
from app.models.enums import DealType, DemandStatus, MatchStatus, PropertyStatus
from app.schemas.matching import (
    ClientDemandCreate,
    ClientDemandListResponse,
    ClientDemandResponse,
    ClientDemandUpdate,
    MatchStatusUpdate,
    PropertyMatchListResponse,
    PropertyMatchResponse,
    RetriggerResponse,
)
from app.services import demand_service, matching_service
from app.services import matching_repository as repo

router = APIRouter()


def _parse_deal(raw: str | None) -> DealType | None:
    if raw is None:
        return None
    try:
        return DealType(raw.strip().upper())
    except ValueError:
        return None


def _parse_demand_status(raw: str | None) -> DemandStatus | None:
    if raw is None:
        return None
    try:
        return DemandStatus(raw.strip().upper())
    except ValueError:
        return None


def _parse_match_status(raw: str | None) -> MatchStatus | None:
    if raw is None:
        return None
    try:
        return MatchStatus(raw.strip().upper())
    except ValueError:
        return None


async def _titles_for(
    session: SessionDep, property_ids: set[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Resolve listing titles for a page of matches in one query."""
    ids = [pid for pid in property_ids if pid]
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(Property.id, Property.title).where(Property.id.in_(ids))
        )
    ).all()
    return {row[0]: row[1] or "" for row in rows}


async def _names_for(
    session: SessionDep, demand_ids: set[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Resolve client names for a page of matches in one query."""
    ids = [did for did in demand_ids if did]
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(ClientDemand.id, ClientDemand.client_name).where(
                ClientDemand.id.in_(ids)
            )
        )
    ).all()
    return {row[0]: row[1] or "" for row in rows}


# ---------------------------------------------------------------------------
#  Demands
# ---------------------------------------------------------------------------
@router.post(
    "/demands",
    response_model=ClientDemandResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a buyer/tenant demand - ثبت نیاز خریدار/مستأجر",
)
async def create_demand(
    payload: ClientDemandCreate, session: SessionDep, _license: LicenseGuard
) -> ClientDemandResponse:
    """Register a new buyer/tenant demand in the matching system.
    
    **فارسی**: ثبت نیاز جدید خریدار یا مستأجر در سیستم تطبیق.
    
    ## پارامترهای اصلی
    - **deal_type** (نوع معامله): SALE (فروش) یا RENT (اجاره)
    - **client_name** (نام مشتری): نام کامل مشتری
    - **client_phone** (تلفن مشتری): شماره تماس
    - **property_type** (نوع ملک): APARTMENT, VILLA, OFFICE, etc.
    - **min_area** (حداقل متراژ): متراژ مورد نیاز حداقلی
    - **max_price** (حداکثر قیمت): بودجه خرید یا اجاره
    - **location_preferences** (ترجیحات موقعیت): شهر، محله
    
    ## وضعیت‌های تقاضا
    - **ACTIVE** (فعال): در حال جستجوی ملک
    - **MATCHED** (تطبیق شده): ملک مناسب یافت شده
    - **CLOSED** (بسته شده): خرید/اجاره انجام شده
    - **CANCELLED** (لغو شده): انصراف مشتری
    """
    try:
        demand = await demand_service.create_demand(session, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_deal_type", "message": str(exc)},
        ) from exc
    return ClientDemandResponse.from_demand(demand)


@router.get(
    "/demands",
    response_model=ClientDemandListResponse,
    summary="List demands (newest first) - لیست نیازها",
)
async def list_demands(
    session: SessionDep,
    _license: LicenseGuard,
    status_filter: str | None = Query(default=None, alias="status", description="فیلتر وضعیت"),
    deal_type: str | None = Query(default=None, description="فیلتر نوع معامله"),
    limit: int = Query(default=50, ge=1, le=200, description="تعداد رکوردها"),
    offset: int = Query(default=0, ge=0, description="شماره شروع"),
) -> ClientDemandListResponse:
    """List all client demands with filtering and pagination.
    
    **فارسی**: لیست نیازهای مشتریان با قابلیت فیلتر و صفحه‌بندی.
    
    ## فیلترهای پشتیبانی شده
    - **status** (وضعیت): ACTIVE, MATCHED, CLOSED, CANCELLED
    - **deal_type** (نوع معامله): SALE, RENT
    - **limit** (محدودیت): تعداد رکورد در هر صفحه (1-200)
    - **offset** (شروع): شماره شروع برای صفحه‌بندی
    
    ## ترتیب نمایش
    - نیازهای جدیدتر ابتدا نمایش داده می‌شوند
    - امکان مرتب‌سازی بر اساس تاریخ ایجاد
    
    ## پاسخ
    - **items**: لیست نیازها
    - **total**: تعداد کل نیازها
    - **limit**: تعداد درخواستی
    - **offset**: نقطه شروع
    """
    st = _parse_demand_status(status_filter)
    if status_filter is not None and st is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_status", "message": f"unknown status {status_filter!r}"},
        )
    dt = _parse_deal(deal_type)
    if deal_type is not None and dt is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_deal_type", "message": f"unknown deal_type {deal_type!r}"},
        )
    items, total = await demand_service.list_demands(
        session, status=st, deal_type=dt, limit=limit, offset=offset
    )
    return ClientDemandListResponse(
        items=[ClientDemandResponse.from_demand(d) for d in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/demands/{demand_id}",
    response_model=ClientDemandResponse,
    summary="Get one demand by id - دریافت یک نیاز",
)
async def get_demand(
    demand_id: uuid.UUID, session: SessionDep, _license: LicenseGuard
) -> ClientDemandResponse:
    demand = await demand_service.get_demand(session, demand_id)
    if demand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "demand_not_found", "demand_id": str(demand_id)},
        )
    return ClientDemandResponse.from_demand(demand)


@router.patch(
    "/demands/{demand_id}",
    response_model=ClientDemandResponse,
    summary="Update a demand - به‌روزرسانی نیاز",
)
async def update_demand(
    demand_id: uuid.UUID,
    payload: ClientDemandUpdate,
    session: SessionDep,
    _license: LicenseGuard,
) -> ClientDemandResponse:
    demand = await demand_service.get_demand(session, demand_id)
    if demand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "demand_not_found", "demand_id": str(demand_id)},
        )
    try:
        demand = await demand_service.update_demand(session, demand, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_update", "message": str(exc)},
        ) from exc
    return ClientDemandResponse.from_demand(demand)


@router.delete(
    "/demands/{demand_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a demand (matches cascade) - حذف نیاز",
)
async def delete_demand(
    demand_id: uuid.UUID, session: SessionDep, _license: LicenseGuard
) -> None:
    demand = await demand_service.get_demand(session, demand_id)
    if demand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "demand_not_found", "demand_id": str(demand_id)},
        )
    await demand_service.delete_demand(session, demand)


@router.post(
    "/demands/{demand_id}/retrigger",
    response_model=RetriggerResponse,
    summary="Re-score the demand - فارسی candidate listings (after widening it) - امتیازدهی مجدد",
)
async def retrigger_demand(
    demand_id: uuid.UUID, session: SessionDep, _license: LicenseGuard
) -> RetriggerResponse:
    demand = await demand_service.get_demand(session, demand_id)
    if demand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "demand_not_found", "demand_id": str(demand_id)},
        )
    counts = await matching_service.retrigger_demand(session, demand)
    return RetriggerResponse(demand_id=demand_id, **counts)


# ---------------------------------------------------------------------------
#  Suggestion queue
# ---------------------------------------------------------------------------
@router.get(
    "/matches",
    response_model=PropertyMatchListResponse,
    summary="Scored suggestions, best first (the agent - فارسی work queue) - لیست پیشنهادات تطبیق",
)
async def list_matches(
    session: SessionDep,
    _license: LicenseGuard,
    demand_id: uuid.UUID | None = Query(default=None, description="شناسه نیاز خاص"),
    property_id: uuid.UUID | None = Query(default=None, description="شناسه ملک خاص"),
    match_status: str | None = Query(default=None, alias="status", description="وضعیت پیشنهاد"),
    limit: int = Query(default=50, ge=1, le=200, description="تعداد رکوردها"),
    offset: int = Query(default=0, ge=0, description="شماره شروع"),
) -> PropertyMatchListResponse:
    """Get scored property suggestions for client demands (best matches first).
    
    **فارسی**: دریافت پیشنهادات امتیازدهی شده املاک برای نیازهای مشتری (بهترین تطابق‌ها اول).
    
    ## توضیحات
    این نقطه پایانی صف کار مشاوران را برمی‌گرداند - پیشنهادات تطبیق شده
    که بر اساس الگوریتم امتیازدهی مرتب شده‌اند.
    
    ## وضعیت‌های پیشنهاد (Match Status)
    - **PENDING** (در انتظار): هنوز بررسی نشده
    - **REVIEWED** (بررسی شده): مشاور آن را دیده است
    - **CONTACTED** (تماس گرفته شده): با مشتری تماس گرفته شده
    - **SHOWED** (نمایش داده شده): ملک به مشتری نشان داده شده
    - **CLOSED** (بسته شده): معامله انجام شده
    - **REJECTED** (رد شده): پیشنهاد رد شده
    
    ## معیارهای امتیازدهی
    - تطابق قیمت با بودجه مشتری
    - تطابق متراژ با نیاز مشتری
    - تطابق موقعیت جغرافیایی
    - تطابق امکانات و ویژگی‌ها
    - تاریخ ایجاد آگهی (آگهی‌های جدیدتر اولویت دارند)
    
    ## فیلترهای پشتیبانی شده
    - **demand_id**: فیلتر بر اساس نیاز خاص
    - **property_id**: فیلتر بر اساس ملک خاص
    - **status**: فیلتر بر اساس وضعیت پیشنهاد
    """
    st = _parse_match_status(match_status)
    if match_status is not None and st is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_status", "message": f"unknown status {match_status!r}"},
        )
    rows, total = await matching_service.list_matches(
        session,
        demand_id=demand_id,
        property_id=property_id,
        status=st,
        limit=limit,
        offset=offset,
    )
    # One batched lookup for the labels instead of N queries per row.
    titles = await _titles_for(session, {row.property_id for row in rows})
    names = await _names_for(session, {row.demand_id for row in rows})
    return PropertyMatchListResponse(
        items=[
            PropertyMatchResponse.from_match(
                row,
                property_title=titles.get(row.property_id, ""),
                demand_name=names.get(row.demand_id, ""),
            )
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/matches/{match_id}",
    response_model=PropertyMatchResponse,
    summary="Move a suggestion through the work queue - تغییر وضعیت پیشنهاد",
)
async def update_match(
    match_id: uuid.UUID,
    payload: MatchStatusUpdate,
    session: SessionDep,
    _license: LicenseGuard,
) -> PropertyMatchResponse:
    st = _parse_match_status(payload.status)
    if st is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_status", "message": f"unknown status {payload.status!r}"},
        )
    match = await session.get(PropertyMatch, match_id)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "match_not_found", "match_id": str(match_id)},
        )
    updated = await matching_service.update_match_status(session, match, st)
    titles = await _titles_for(session, {updated.property_id})
    names = await _names_for(session, {updated.demand_id})
    return PropertyMatchResponse.from_match(
        updated,
        property_title=titles.get(updated.property_id, ""),
        demand_name=names.get(updated.demand_id, ""),
    )
