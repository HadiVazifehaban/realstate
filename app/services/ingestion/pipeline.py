"""End-to-end Divar ingestion orchestrator (Phase 2).

Flow per listing::

    search page -> parse summaries -> fetch detail -> dedupe
        -> sanitize -> persist Property + encrypted PII -> emit event

The pipeline is deliberately decoupled: it emits ``NewPropertyIngested`` and the
Phase 3 matching engine subscribes to it, so ingestion never blocks on matching.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import Settings, get_settings
from app.core.crypto import PiiCipher
from app.core.logging import get_logger
from app.models import Property, PropertyMedia, PropertyOwnerPII, ScrapeJob
from app.models.base import utcnow
from app.models.enums import MediaType, PropertySource, ScrapeJobStatus
from app.services.events import NEW_PROPERTY_INGESTED, event_bus
from app.services.ingestion.deduplicator import compute_content_hash, find_duplicate
from app.services.ingestion.sanitizer import build_property_fields
from app.services.scraper.parser import DivarListingDetail
from app.services.scraper.registry import ScraperSource

logger = get_logger("app.ingestion")

STATUS_NEW = "NEW"
STATUS_UPDATED = "UPDATED"
STATUS_DUPLICATE = "DUPLICATE"
STATUS_FAILED = "FAILED"

# Divar serves the same photo as both .jpg and .webp; the model default is
# image/webp, so only the exceptions need naming.
_IMAGE_MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def _image_mime(url: str) -> str:
    path = url.split("?", 1)[0].lower()
    for ext, mime in _IMAGE_MIME_BY_EXT.items():
        if path.endswith(ext):
            return mime
    return "image/webp"


@dataclass
class IngestionOutcome:
    """Result of processing a single listing."""

    status: str
    property_id: uuid.UUID | None = None
    content_hash: str | None = None
    error: str | None = None

    @property
    def is_new(self) -> bool:
        return self.status == STATUS_NEW

    @property
    def is_duplicate(self) -> bool:
        return self.status in (STATUS_DUPLICATE, STATUS_UPDATED)


async def store_owner_pii(
    session: AsyncSession,
    property_id: uuid.UUID,
    detail: DivarListingDetail,
    cipher: PiiCipher,
    *,
    created_by_id: uuid.UUID | None = None,
) -> PropertyOwnerPII | None:
    """Encrypt the scraped phone number straight into the Phase 1 PII vault."""
    if not detail.phone:
        return None
    pii = PropertyOwnerPII(
        property_id=property_id,
        owner_phone_enc=cipher.encrypt(detail.phone),
        owner_phone_bindex=cipher.blind_index(detail.phone),
        owner_name_enc=None,
        created_by_id=created_by_id,
    )
    session.add(pii)
    return pii


async def _upsert_pii(
    session: AsyncSession,
    property_id: uuid.UUID,
    detail: DivarListingDetail,
    cipher: PiiCipher,
) -> None:
    """Create or refresh the encrypted PII row for a property.

    A re-scrape without an extracted phone must never wipe a previously
    stored number, so ``None`` phones are a deliberate no-op.
    """
    if not detail.phone:
        return
    existing = (
        await session.exec(
            select(PropertyOwnerPII).where(PropertyOwnerPII.property_id == property_id)
        )
    ).first()
    if existing is not None:
        existing.owner_phone_enc = cipher.encrypt(detail.phone)
        existing.owner_phone_bindex = cipher.blind_index(detail.phone)
        existing.updated_at = utcnow()
        return
    await store_owner_pii(session, property_id, detail, cipher)


async def sync_property_media(
    session: AsyncSession, property_id: uuid.UUID, images: list[str]
) -> int:
    """Attach any gallery image the listing does not already have.

    Additive and idempotent: rows are matched on ``cloud_url``, so a re-scrape
    adds only what Divar has since published and never duplicates the rest. The
    first URL is flagged ``is_cover`` -- the parser puts Divar's own
    ``post_seo_schema.image`` there, which is the listing photo rather than the
    agency logo ``collect_images`` would otherwise lead with.

    Crawled photos are stored straight into ``cloud_url``: they are absolute CDN
    URLs the browser can fetch, whereas ``local_path`` names a file on this
    node's disk and would render as a broken image.
    """
    if not images:
        return 0
    existing = (
        await session.exec(
            select(PropertyMedia).where(PropertyMedia.property_id == property_id)
        )
    ).all()
    known = {row.cloud_url for row in existing if row.cloud_url}

    added = 0
    for order, url in enumerate(images):
        if url in known:
            continue
        known.add(url)
        session.add(
            PropertyMedia(
                property_id=property_id,
                media_type=MediaType.IMAGE,
                cloud_url=url,
                mime_type=_image_mime(url),
                is_cover=order == 0,
                sort_order=order,
            )
        )
        added += 1

    if added:
        await session.flush()
    return added


async def process_detail(
    session: AsyncSession,
    detail: DivarListingDetail,
    *,
    cipher: PiiCipher,
    settings: Settings | None = None,
    existing: Property | None = None,
    property_source: PropertySource = PropertySource.DIVAR_SCRAPER,
    external_id_prefix: str = "",
) -> IngestionOutcome:
    """Deduplicate + persist one parsed listing (and its encrypted phone).

    ``property_source`` stamps the row with the portal it came from, so a
    Sheypoor listing is never filed as a Divar one. It defaults to Divar because
    that is what every caller before the source registry did.

    ``external_id_prefix`` namespaces the dedup key. ``external_id`` carries a
    globally unique index, so two portals that both number their listings would
    otherwise overwrite each other; a new source must therefore set a prefix.
    Divar keeps the bare token because its rows are already stored that way.
    """
    settings = settings or get_settings()
    price = detail.total_price if detail.total_price is not None else detail.deposit
    content_hash = compute_content_hash(
        detail.city, detail.district, detail.area, detail.floor, price
    )
    external_id = f"{external_id_prefix}{detail.token}" if external_id_prefix else detail.token

    try:
        duplicate = existing or await find_duplicate(
            session, external_id=external_id, content_hash=content_hash
        )
        fields = build_property_fields(
            detail,
            content_hash=content_hash,
            storage_node_id=settings.node_mode.value.lower(),
            source=property_source,
        )

        if duplicate is not None:
            for key, value in fields.items():
                setattr(duplicate, key, value)
            duplicate.updated_at = utcnow()
            await _upsert_pii(session, duplicate.id, detail, cipher)
            await sync_property_media(session, duplicate.id, detail.images)
            await session.commit()
            return IngestionOutcome(STATUS_UPDATED, duplicate.id, content_hash)

        prop = Property(**fields)
        session.add(prop)
        await session.flush()  # assign id before creating the child rows
        await _upsert_pii(session, prop.id, detail, cipher)
        await sync_property_media(session, prop.id, detail.images)
        await session.commit()

        # Fire-and-forget: Phase 3 matching subscribers react here.
        await event_bus.emit(
            NEW_PROPERTY_INGESTED, session=session, property_id=prop.id
        )
        return IngestionOutcome(STATUS_NEW, prop.id, content_hash)

    except Exception as exc:  # noqa: BLE001 - one bad listing must not kill a job
        await session.rollback()
        logger.warning("ingestion failed for %s: %s", detail.token, exc)
        return IngestionOutcome(STATUS_FAILED, None, content_hash, error=str(exc))


async def run_search_job(
    session: AsyncSession,
    job: ScrapeJob,
    *,
    client: Any,
    cipher: PiiCipher,
    source: ScraperSource,
    settings: Settings | None = None,
    phone_extractor: Any | None = None,
    max_pages: int = 1,
) -> ScrapeJob:
    """Execute a SEARCH scrape job: list -> detail -> dedupe -> persist.

    ``source`` carries the client parsers and the ``PropertySource`` to stamp, so
    this function is portal-agnostic: nothing here names Divar. It is a required
    argument rather than a defaulted one on purpose -- the old module-level
    import made every caller silently Divar-only, which is how Sheypoor ended up
    written, tested and unreachable.
    """
    settings = settings or get_settings()
    city = job.city or (settings.city_list[0] if settings.city_list else "")
    category = job.category or (
        settings.category_list[0] if settings.category_list else ""
    )
    if source.key == "sheypoor":
        from app.services.scraper.category_mapping import resolve_categories

        try:
            category = resolve_categories("sheypoor", category).categories[0]
        except ValueError:
            # Source-owned category slugs (e.g. bounded demand tasks) are
            # already validated by create_job and retained in job params.
            pass
    districts = list((job.params or {}).get("districts") or [])

    job.status = ScrapeJobStatus.RUNNING
    job.started_at = utcnow()
    job.updated_at = utcnow()
    await session.commit()

    try:
        for page in range(1, max_pages + 1):
            payload = await client.search(city, category, page, districts=districts or None)
            summaries = source.parse_search(payload)
            from app.services.market_demand import filter_source_summaries
            summaries = await filter_source_summaries(source.key, city, summaries)
            job.pages_scraped += 1
            job.items_found += len(summaries)
            if not summaries:
                break

            for summary in summaries:
                try:
                    detail_payload = await client.get_post(summary.token)
                    phone = None
                    if phone_extractor is not None:
                        phone = await phone_extractor.extract(
                            summary.token, client=client
                        )
                    detail = source.parse_detail(
                        detail_payload, summary.token, phone=phone
                    )
                    if source.key in ("delta", "sheypoor"):
                        from app.services.location_catalog import normalized_name
                        from app.services.scraper.demand_locations import canonical_demand_city

                        expected = canonical_demand_city(city)
                        actual = resolve_city(detail.city, detail.province) if detail.city else None
                        if detail.city and actual is None:
                            # A non-empty but unresolved detail value is not
                            # evidence for replacing it with the search city.
                            job.items_failed += 1
                            continue
                        if actual:
                            detail.city, detail.province = actual["name"], actual["province"]
                            if expected and normalized_name(actual["name"]) != normalized_name(expected["name"]):
                                job.items_failed += 1
                                continue
                        elif source.key == "sheypoor" and not (detail_payload.get("city") or detail_payload.get("city_slug")):
                            # The exact source search result is city-scoped and
                            # the client retained that listing's search city.
                            search_city = resolve_city(str(detail_payload.get("__search_city") or ""))
                            if expected and search_city and normalized_name(search_city["name"]) == normalized_name(expected["name"]):
                                detail.city, detail.province = expected["name"], expected["province"]
                    outcome = await process_detail(
                        session,
                        detail,
                        cipher=cipher,
                        settings=settings,
                        property_source=source.property_source,
                        external_id_prefix=source.external_id_prefix,
                    )
                    if outcome.is_new:
                        job.items_new += 1
                    elif outcome.is_duplicate:
                        job.items_duplicate += 1
                    else:
                        job.items_failed += 1
                except Exception as exc:  # noqa: BLE001
                    job.items_failed += 1
                    logger.warning("detail scrape failed for %s: %s", summary.token, exc)

            job.updated_at = utcnow()
            await session.commit()

        job.status = ScrapeJobStatus.COMPLETED
    except Exception as exc:  # noqa: BLE001
        job.status = ScrapeJobStatus.FAILED
        job.error = str(exc)[:1000]
        logger.warning("scrape job %s failed: %s", job.id, exc)
    finally:
        job.finished_at = utcnow()
        job.updated_at = utcnow()
        await session.commit()

    return job
