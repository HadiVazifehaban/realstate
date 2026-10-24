"""Statistics endpoints for dashboard overview."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.models.agency_user import AgencyUser
from app.models.property import Property
from app.models.client_demand import ClientDemand
from app.models.enums import DealType, PropertyStatus

router = APIRouter()


@router.get("/overview")
async def get_overview_statistics(session: SessionDep):
    """
    Get overview statistics for the dashboard.
    Returns aggregate statistics about properties, agencies, users, and requests.
    """
    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Property statistics
    try:
        total_listings = await session.scalar(select(func.count(Property.id)))
    except Exception:
        total_listings = 0

    try:
        showcase_buy = await session.scalar(
            select(func.count(Property.id))
            .where(Property.deal_type == DealType.SALE)
            .where(Property.status == PropertyStatus.ACTIVE)
        )
    except Exception:
        showcase_buy = 0

    try:
        showcase_rent = await session.scalar(
            select(func.count(Property.id))
            .where(Property.deal_type == DealType.RENT)
            .where(Property.status == PropertyStatus.ACTIVE)
        )
    except Exception:
        showcase_rent = 0

    try:
        radar_deals = await session.scalar(
            select(func.count(Property.id))
            .where(Property.is_below_market == True)
        )
    except Exception:
        radar_deals = 0

    try:
        new_today = await session.scalar(
            select(func.count(Property.id))
            .where(Property.created_at >= today_start)
        )
    except Exception:
        new_today = 0

    # Agency statistics
    try:
        total_agencies = await session.scalar(
            select(func.count(func.distinct(AgencyUser.agency_name)))
        )
    except Exception:
        total_agencies = 0

    try:
        active_agencies = await session.scalar(
            select(func.count(func.distinct(AgencyUser.agency_name)))
            .where(AgencyUser.is_active == True)
        )
    except Exception:
        active_agencies = 0

    try:
        new_agencies_month = await session.scalar(
            select(func.count(func.distinct(AgencyUser.agency_name)))
            .where(AgencyUser.created_at >= month_ago)
        )
    except Exception:
        new_agencies_month = 0

    # Top agencies
    top_agencies_list = []
    try:
        top_agencies_query = (
            select(
                AgencyUser.agency_name,
                func.count(Property.id).label("listings_count"),
                Property.city
            )
            .outerjoin(Property, AgencyUser.user_id == Property.created_by_id)
            .group_by(AgencyUser.agency_name, Property.city)
            .order_by(func.count(Property.id).desc())
            .limit(5)
        )
        top_agencies = (await session.execute(top_agencies_query)).fetchall()
        top_agencies_list = [
            {
                "name": row.agency_name or "ناشناس",
                "listings_count": row.listings_count or 0,
                "city": row.city or "ناشناس"
            }
            for row in top_agencies
        ]
    except Exception:
        top_agencies_list = []

    # User statistics
    try:
        total_users = await session.scalar(select(func.count(AgencyUser.id)))
    except Exception:
        total_users = 0

    try:
        active_brokers = await session.scalar(
            select(func.count(AgencyUser.id))
            .where(AgencyUser.is_active == True)
        )
    except Exception:
        active_brokers = 0

    try:
        new_users_month = await session.scalar(
            select(func.count(AgencyUser.id))
            .where(AgencyUser.created_at >= month_ago)
        )
    except Exception:
        new_users_month = 0

    # Top brokers
    top_brokers_list = []
    try:
        top_brokers_query = (
            select(
                AgencyUser.full_name,
                func.count(Property.id).label("listings_count"),
                Property.city
            )
            .outerjoin(Property, AgencyUser.user_id == Property.created_by_id)
            .group_by(AgencyUser.full_name, Property.city)
            .order_by(func.count(Property.id).desc())
            .limit(5)
        )
        top_brokers = (await session.execute(top_brokers_query)).fetchall()
        top_brokers_list = [
            {
                "name": row.full_name or "ناشناس",
                "listings_count": row.listings_count or 0,
                "city": row.city or "ناشناس"
            }
            for row in top_brokers
        ]
    except Exception:
        top_brokers_list = []

    # Request statistics
    try:
        total_requests = await session.scalar(select(func.count(ClientDemand.id)))
    except Exception:
        total_requests = 0

    try:
        pending_requests = await session.scalar(
            select(func.count(ClientDemand.id))
            .where(ClientDemand.status == "pending")
        )
    except Exception:
        pending_requests = 0

    try:
        completed_requests = await session.scalar(
            select(func.count(ClientDemand.id))
            .where(ClientDemand.status == "completed")
        )
    except Exception:
        completed_requests = 0

    try:
        new_requests_today = await session.scalar(
            select(func.count(ClientDemand.id))
            .where(ClientDemand.created_at >= today_start)
        )
    except Exception:
        new_requests_today = 0

    # Financial statistics (mock for now - would come from payments/invoices)
    revenue_this_month = 125000000  # Mock data
    revenue_this_year = 890000000  # Mock data

    # Properties by city
    by_city_list = []
    try:
        by_city_query = (
            select(Property.city, func.count(Property.id).label("count"))
            .group_by(Property.city)
            .order_by(func.count(Property.id).desc())
            .limit(6)
        )
        by_city = (await session.execute(by_city_query)).fetchall()
        by_city_list = [
            {"city": row.city or "ناشناس", "count": row.count or 0}
            for row in by_city
        ]
    except Exception:
        by_city_list = []

    # Properties by type
    by_type_list = []
    try:
        by_type_query = (
            select(Property.property_type, func.count(Property.id).label("count"))
            .group_by(Property.property_type)
            .order_by(func.count(Property.id).desc())
            .limit(5)
        )
        by_type = (await session.execute(by_type_query)).fetchall()
        by_type_list = [
            {"type": row.property_type or "ناشناس", "count": row.count or 0}
            for row in by_type
        ]
    except Exception:
        by_type_list = []

    # Properties by status
    by_status_list = []
    try:
        by_status_query = (
            select(Property.deal_type, func.count(Property.id).label("count"))
            .group_by(Property.deal_type)
            .order_by(func.count(Property.id).desc())
            .limit(4)
        )
        by_status = (await session.execute(by_status_query)).fetchall()
        by_status_list = [
            {"status": str(row.deal_type) if row.deal_type else "ناشناس", "count": row.count or 0}
            for row in by_status
        ]
    except Exception:
        by_status_list = []

    # Featured listings (most viewed)
    featured_listings_list = []
    try:
        featured_query = (
            select(Property)
            .order_by(Property.views.desc().nulls_last())
            .limit(4)
        )
        featured_listings = (await session.execute(featured_query)).scalars().all()
        featured_listings_list = [
            {
                "id": str(prop.id),
                "title": prop.title or "بدون عنوان",
                "price": prop.total_price or 0,
                "city": prop.city or "ناشناس",
                "type": prop.property_type or "ناشناس",
                "status": str(prop.deal_type) if prop.deal_type else "ناشناس",
                "views": prop.views or 0
            }
            for prop in featured_listings
        ]
    except Exception:
        featured_listings_list = []

    return {
        "stats": {
            "total_listings": total_listings or 0,
            "showcase_buy": showcase_buy or 0,
            "showcase_rent": showcase_rent or 0,
            "radar_deals": radar_deals or 0,
            "new_today": new_today or 0,
            "trends": {
                "total_listings": 8.5,  # Mock trend
                "showcase_buy": 12.3,
                "showcase_rent": -5.2,
                "radar_deals": 23.1
            }
        },
        "agency_stats": {
            "total_agencies": total_agencies or 0,
            "active_agencies": active_agencies or 0,
            "new_this_month": new_agencies_month or 0,
            "top_agencies": top_agencies_list
        },
        "user_stats": {
            "total_users": total_users or 0,
            "active_brokers": active_brokers or 0,
            "new_this_month": new_users_month or 0,
            "top_brokers": top_brokers_list
        },
        "request_stats": {
            "total_requests": total_requests or 0,
            "pending": pending_requests or 0,
            "completed": completed_requests or 0,
            "new_today": new_requests_today or 0
        },
        "financial_stats": {
            "revenue_this_month": revenue_this_month,
            "revenue_this_year": revenue_this_year,
            "trend_month": 15.5
        },
        "by_city": by_city_list,
        "by_type": by_type_list,
        "by_status": by_status_list,
        "featured_listings": featured_listings_list,
        "news": [
            {
                "id": "1",
                "title": "سیستم رادار شکار قیمت به‌روزرسانی شد",
                "content": "الگوریتم جدید برای شناسایی فرصت‌های زیر بازار اضافه شد",
                "published_at": (now - timedelta(hours=24)).isoformat(),
                "is_important": True
            },
            {
                "id": "2",
                "title": "گزارش ماهانه درآمد منتشر شد",
                "content": "گزارش کامل درآمد ماهانه در بخش گزارش‌ها موجود است",
                "published_at": (now - timedelta(hours=72)).isoformat(),
                "is_important": False
            }
        ],
        "recent_activities": []  # Would come from activity logs
    }
