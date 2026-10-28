"""Divar autonomous scraper endpoints (Phase 2).

All operations sit behind the Phase 1 commercial license guard
(``verify_license_active``): without an ACTIVE/GRACE license the scraper
cannot be started or inspected.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import LicenseGuard, SessionDep, SettingsDep
from app.schemas.scraper import (
    ScrapeJobCreate,
    ScrapeJobListResponse,
    ScrapeJobResponse,
    ScrapeStatsResponse,
)
from app.services import scraper_service
from app.services.scraper.registry import UnknownSourceError, get_source
from app.services.scraper.category_mapping import JobValidationError, validate_job_target
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

    # Validate every requested target with the same central gate as all other
    # job-creation paths before queueing the first city.
    try:
        for city in requested:
            validate_job_target(source.key, city, category, settings)
            if payload.districts and source.validate_districts is not None:
                source.validate_districts(city, payload.districts)
    except (JobValidationError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": getattr(exc, "code", "unknown_city_or_district"), "message": str(exc)},
        ) from exc

    # One sweep per city, all queued before returning, so a six-city filter is
    # six jobs the caller can watch rather than one long one they cannot.
    jobs = []
    dry_run = payload.params.get("dry_run") is True
    for city in requested:
        single = payload.model_copy(update={"city": city, "cities": []})
        if dry_run:
            try:
                await scraper_service.trigger_and_maybe_run(session, single, settings=settings, wait=False)
            except JobValidationError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": exc.code, "message": str(exc)},
                ) from exc
            continue
        try:
            job = await scraper_service.trigger_and_maybe_run(
                session, single, settings=settings, wait=False
            )
            if job is not None:
                jobs.append(job)
        except JobValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": exc.code, "message": str(exc)},
            ) from exc

    if dry_run:
        return {"status": "validated", "queued": 0, "cities": requested, "source": source.key, "category": category}

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

    from app.services.scraper.demand_locations import demand_location

    if demand_location(city) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "unknown_focus_city", "message": "City is not in the curated location catalog."},
        )
    
    # Check if city is supported
    if not settings.scraper_enabled:
        return {
            "status": "skipped",
            "message": "Scraper is disabled. Enable SCRAPER_ENABLED=true to activate.",
            "city": city,
        }
    
    # This endpoint persists only the user's focus preference in client state;
    # it must not create jobs or start scraping as a side effect.
    return {
        "status": "success",
        "city": city,
        "message": "Focus city selected; no scrape job was created.",
    }


__all__ = ["router"]
