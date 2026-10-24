"""FastAPI application factory.

Serves both topologies from one codebase:

* ``NODE_MODE=LOCAL``      -> the on-premise office node (also serves the LAN UI).
* ``NODE_MODE=CLOUD_HUB``  -> the central AVG SaaS hub.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __app_name__, __brand_owner__, __version__
from app.api.deps import PrincipalDep
from app.api.v1.router import api_router
from app.core.config import NodeMode, get_settings
from app.core.identity import IdentityError
from app.core.logging import configure_logging, get_logger

logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    sms_factory = None
    if settings.sms_provider.strip().lower() == "melli-payamak":
        from app.services.sms_provider import DisabledSmsProvider

        if not settings.mellipayamak_enabled:
            app.state.sms_provider = DisabledSmsProvider("MelliPayamak delivery is not approved/enabled")
        else:
            from app.services.melli_payamak import MelliPayamakSmsSenderProviderFactory

            sms_factory = MelliPayamakSmsSenderProviderFactory(settings)
            app.state.sms_provider = sms_factory.provider
    configure_logging(debug=settings.debug)
    settings.ensure_directories()
    logger.info(
        "startup",
        extra={
            "node_mode": settings.node_mode.value,
            "event": "app_startup",
        },
    )

    # Best-effort license sync: the node must still boot if the DB is briefly
    # unavailable (offline-first requirement).
    try:
        from app.db.session import AsyncSessionLocal
        from app.services import license_service

        async with AsyncSessionLocal() as session:
            row = await license_service.sync_license_from_disk(session, settings)
            logger.info(
                "license evaluated: %s", row.status,
                extra={"license_status": str(row.status)},
            )
    except Exception as exc:  # noqa: BLE001 - never block boot
        logger.warning("License sync skipped at startup: %s", exc)

    # Fail any scrape job left mid-flight by a previous process. Jobs run as
    # in-process asyncio tasks, so a restart orphans them; without this the
    # scheduler's overlap guard would treat the zombie as active and never
    # schedule another sweep.
    if settings.scraper_enabled:
        try:
            from app.db.session import AsyncSessionLocal
            from app.services import scraper_service

            async with AsyncSessionLocal() as session:
                await scraper_service.recover_orphaned_jobs(session)
        except Exception as exc:  # noqa: BLE001 - never block boot
            logger.warning("Orphaned scrape-job recovery skipped: %s", exc)

    # Autonomous scrape scheduler (Phase 2b). Off by default; when enabled it
    # self-gates on the license, so an unlicensed node stays idle.
    scheduler = None
    if settings.scraper_enabled and settings.scraper_scheduler_enabled:
        try:
            from app.services.scraper_scheduler import build_scheduler

            scheduler = build_scheduler(settings)
            scheduler.start()
            logger.info(
                "scrape scheduler enabled",
                extra={"event": "scheduler_started", "interval_min": settings.scraper_schedule_interval_minutes},
            )
        except Exception as exc:  # noqa: BLE001 - never block boot
            logger.warning("Scraper scheduler not started: %s", exc)
    else:
        logger.info("scrape scheduler disabled")

    # Matching engine (Phase 3): subscribe the scorer to newly ingested
    # listings. Registration is idempotent, so repeated boots are safe.
    try:
        from app.services import matching_service

        matching_service.register_matching_subscriber()
    except Exception as exc:  # noqa: BLE001 - never block boot
        logger.warning("Matching subscriber not registered: %s", exc)

    # AVM (Phase 3b): value each listing as it lands, otherwise a crawled unit
    # would stay UNKNOWN forever and never reach the bargain radar.
    try:
        from app.services import valuation

        valuation.register_valuation_subscriber()
    except Exception as exc:  # noqa: BLE001 - never block boot
        logger.warning("Valuation subscriber not registered: %s", exc)

    yield

    if sms_factory is not None:
        await sms_factory.aclose()

    if scheduler is not None:
        try:
            await scheduler.stop()
        except Exception as exc:  # noqa: BLE001 - shutdown must not raise
            logger.warning("Scraper scheduler stop failed: %s", exc)
    logger.info("shutdown", extra={"event": "app_shutdown"})


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=__app_name__,
        version=__version__,
        description=(
            f"{__brand_owner__} — Hybrid Edge/Cloud real-estate CRM & MLS platform."
        ),
        # Keep API schemas out of anonymous HTTP routes. Developers and tests
        # can still call ``app.openapi()`` in-process.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    # The office node is accessed over the LAN (Wi-Fi) by phones/tablets.
    _allow_all = settings.is_local_node
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if _allow_all else [settings.cloud_hub_base_url],
        allow_credentials=not _allow_all,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    )

    @app.middleware("http")
    async def _security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=()")
        if request.url.path.startswith("/api/v1/") or request.url.path == "/api/v1":
            response.headers.setdefault("Cache-Control", "private, no-store, max-age=0")
            response.headers.setdefault("Vary", "Authorization")
        return response

    # Any identity gate (KYC approval, role ladder, PII vault) raises IdentityError.
    # Registered app-wide so a gate raised inside a dependency -- not just inside a
    # route body -- still answers with its own status and Persian message instead
    # of escaping as a 500.
    @app.exception_handler(IdentityError)
    async def _identity_error_handler(_request: Request, exc: IdentityError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"error": exc.code, "message": exc.message}},
        )

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/", tags=["meta"], summary="Service banner")
    async def root(_principal: PrincipalDep) -> dict:
        return {
            "app": __app_name__,
            "version": __version__,
            "brand_owner": __brand_owner__,
            "node_mode": settings.node_mode.value,
            "domains": list(settings.brand_domains),
            "ai_engine": settings.feature_flag_ai_engine,
            "docs": None,
        }

    return app


app = create_app()
