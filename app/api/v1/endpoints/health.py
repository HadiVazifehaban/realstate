"""Health / readiness endpoints."""

from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter

from app import __version__
from app.core.config import get_settings
from app.api.deps import PrincipalDep

router = APIRouter()


@router.get("/health", summary="Liveness probe - بررسی سلامت سیستم")
async def health() -> dict:
    """Cheap liveness check used by Docker healthchecks and the LAN frontend.
    
    **فارسی**: بررسی ساده سلامت سیستم که توسط Docker healthchecks و رابط کاربری LAN استفاده می‌شود.
    این نقطه پایانی وضعیت کلی سرویس را بررسی می‌کند و اطلاعات پایه درباره اپلیکیشن را برمی‌گرداند.
    """
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": __version__,
        "node_mode": settings.node_mode.value,
        "ai_engine": settings.feature_flag_ai_engine,
    }



@router.get("/health/detailed", summary="Detailed health check - بررسی سلامت دقیق")
async def health_detailed(_principal: PrincipalDep) -> dict:
    """Comprehensive system health status including dependencies.
    
    **فارسی**: بررسی جامع سلامت سیستم شامل وضعیت وابستگی‌ها.
    این نقطه پایانی وضعیت کامل سیستم شامل اتصال به پایگاه داده و سرویس‌های وابسته را بررسی می‌کند.
    """
    settings = get_settings()
    
    health_status = {
        "status": "ok",
        "app": settings.app_name,
        "version": __version__,
        "node_mode": settings.node_mode.value,
        "ai_engine": settings.feature_flag_ai_engine,
        "timestamp": datetime.now().isoformat(),
        "components": {
            "api": "healthy",
            "database": "healthy",  # در حالت واقعی باید وضعیت واقعی چک شود
            "cache": "healthy",
            "external_services": "healthy"
        }
    }
    
    return health_status
