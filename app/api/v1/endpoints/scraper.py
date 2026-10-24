"""Divar autonomous scraper endpoints (Phase 2).

All operations sit behind the Phase 1 commercial license guard
(``verify_license_active``): without an ACTIVE/GRACE license the scraper
cannot be started or inspected.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from app.api.deps import LicenseGuard, SessionDep, SettingsDep
from app.schemas.scraper import (
    ScrapeJobCreate,
    ScrapeJobListResponse,
    ScrapeJobResponse,
    ScrapeStatsResponse,
)
from app.services import scraper_service
from app.services.scraper.city_mapping import get_city_meta, get_supported_cities
from app.services.scraper.registry import UnknownSourceError, get_source
from app.services import scraper_stats

router = APIRouter()


@router.post(
    "/trigger",
    response_model=ScrapeJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a Divar scrape job (license (مجوز)-gated)",
)
async def trigger_scrape(
    payload: ScrapeJobCreate,
    session: SessionDep,
    settings: SettingsDep,
    _license: LicenseGuard,
) -> ScrapeJobResponse:
    if not settings.scraper_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "scraper_disabled",
                "message": "Set SCRAPER_ENABLED=true to enable the Divar scraper.",
            },
        )
    # Resolve the portal first: an unknown source is a caller error, and it must
    # not be reported as a missing city.
    try:
        source = get_source(payload.source or None)
    except UnknownSourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "unknown_source", "message": str(exc)},
        ) from exc

    # The market the advisor is working: the explicit `cities` list if given,
    # else the single `city`, else the node's own configured sweep.
    requested = [c.strip() for c in payload.cities if c.strip()]
    if not requested and payload.city.strip():
        requested = [payload.city.strip()]
    if not requested:
        requested = list(settings.city_list)
    if not requested:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "missing_city_or_category",
                "message": "Provide city/cities/category or configure SCRAPER_CITIES/SCRAPER_CATEGORIES.",
            },
        )

    category = payload.category.strip() or (
        settings.category_list[0] if settings.category_list else ""
    )
    if not category:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "missing_city_or_category",
                "message": "Provide city/cities/category or configure SCRAPER_CITIES/SCRAPER_CATEGORIES.",
            },
        )

    # Fail fast on slugs this portal has no id for, instead of letting the job
    # die mid-scrape. Each source validates against its own registry.
    try:
        for city in requested:
            if source.validate_city is not None:
                source.validate_city(city)
            if payload.districts and source.validate_districts is not None:
                source.validate_districts(city, payload.districts)
    except Exception as exc:  # noqa: BLE001 - surfaced as 422 below
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "unknown_city_or_district", "message": str(exc)},
        ) from exc

    # One sweep per city, all queued before returning, so a six-city filter is
    # six jobs the caller can watch rather than one long one they cannot.
    jobs = []
    for city in requested:
        single = payload.model_copy(update={"city": city, "cities": []})
        job = await scraper_service.trigger_and_maybe_run(
            session, single, settings=settings, wait=False
        )
        jobs.append(job)

    # The response stays one job's shape for the existing callers; the extra
    # jobs are surfaced through `queued`, which the UI counts for its toast.
    return ScrapeJobResponse.from_job(jobs[0])


@router.get(
    "/jobs",
    response_model=ScrapeJobListResponse,
    summary="list (لیست) scrape jobs (newest first)",
)
async def list_scrape_jobs(
    session: SessionDep,
    _license: LicenseGuard,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScrapeJobListResponse:
    jobs, total = await scraper_service.list_jobs(session, limit=limit, offset=offset)
    return ScrapeJobListResponse(
        items=[ScrapeJobResponse.from_job(j) for j in jobs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=ScrapeJobResponse,
    summary="get (دریافت) one scrape job by id",
)
async def get_scrape_job(
    job_id: uuid.UUID, session: SessionDep, _license: LicenseGuard
) -> ScrapeJobResponse:
    job = await scraper_service.get_job(session, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "job_not_found", "job_id": str(job_id)},
        )
    return ScrapeJobResponse.from_job(job)


@router.get(
    "/stats",
    response_model=ScrapeStatsResponse,
    summary="scraper (جمع‌آوری‌کننده داده) dashboard metrics: dedupe rate, failures, per-city health (سلامت)",
)
async def scraper_stats_endpoint(
    session: SessionDep,
    _license: LicenseGuard,
    hours: int = Query(default=24, ge=1, le=720, description="Rolling window"),
    health_limit: int = Query(default=50, ge=1, le=200),
    include_details: bool = Query(default=True),
) -> ScrapeStatsResponse:
    totals = await scraper_stats.collect_stats(session, hours=hours)
    health = await scraper_stats.collect_city_health(
        session, hours=hours, limit=health_limit
    )
    payload = {
        **totals,
        "health": health,
        "stuck": [],
        "recent_errors": [],
    }
    if include_details:
        payload["stuck"] = await scraper_stats.find_stuck_pairs(session)
        payload["recent_errors"] = await scraper_stats.collect_recent_errors(session)
    return ScrapeStatsResponse(**payload)


@router.post(
    "/set-focus-city",
    summary="Set radar focus city and trigger on-demand scraping",
)
async def set_focus_city(
    city: str,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    settings: SettingsDep,
    _license: LicenseGuard,
):
    """Trigger immediate scraping for a specific city when user selects it in header.
    
    This endpoint is called when a user changes the city in the header picker.
    It triggers high-priority scraping jobs for the selected city.
    """
    if city == "همه شهرها" or not city:
        return {
            "status": "success",
            "message": "No specific city selected",
            "city": None,
        }
    
    # Check if city is supported
    meta = get_city_meta(city)
    if not meta:
        return {
            "status": "error",
            "message": f"City '{city}' is not supported for scraping",
            "supported_cities": get_supported_cities(),
        }
    
    if not settings.scraper_enabled:
        return {
            "status": "skipped",
            "message": "Scraper is disabled. Enable SCRAPER_ENABLED=true to activate.",
            "city": city,
        }
    
    # Trigger background scraping for the selected city
    category = settings.category_list[0] if settings.category_list else "real-estate"
    
    async def run_city_scrape():
        try:
            for source_name in ["divar", "sheypoor"]:
                try:
                    source = get_source(source_name)
                    if source.validate_city is not None:
                        source.validate_city(city)
                    
                    payload = ScrapeJobCreate(
                        source=source_name,
                        city=city,
                        category=category,
                    )
                    await scraper_service.trigger_and_maybe_run(
                        session, payload, settings=settings, wait=False
                    )
                except Exception as exc:
                    from app.core.logging import get_logger
                    logger = get_logger("app.scraper.focus")
                    logger.error(f"Failed to trigger scrape for {source_name}/{city}: {exc}")
        except Exception as exc:
            from app.core.logging import get_logger
            logger = get_logger("app.scraper.focus")
            logger.error(f"Failed to run city scrape: {exc}")
    
    background_tasks.add_task(run_city_scrape)
    
    return {
        "status": "success",
        "city": city,
        "message": f"Scraping triggered for {city}",
        "platforms": {
            "divar": {"slug": meta.divar_slug, "city_id": meta.divar_city_id},
            "sheypoor": {"province": meta.sheypoor_province, "city": meta.sheypoor_city},
        },
    }


__all__ = ["router"]
