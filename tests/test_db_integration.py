"""Database integration tests (PostGIS + license persistence).

These run only when a migrated PostgreSQL/PostGIS database is reachable; they
are skipped otherwise so the pure unit suite always passes offline.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from app.core.config import Settings
from app.core.licensing import LicensePayload, encode_license, generate_keypair
from app.db.session import AsyncSessionLocal, engine
from app.models import ClientDemand, Property
from app.models.node_license import NodeLicense
from app.services import license_service


async def _db_ready() -> bool:
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT to_regclass('public.property') IS NOT NULL")
            )
            return bool(result.scalar())
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture()
async def db_ready() -> bool:
    if not await _db_ready():
        pytest.skip("PostgreSQL/PostGIS not available")


async def test_postgis_contains_spatial_query(db_ready) -> None:
    async with AsyncSessionLocal() as session:
        prop = Property(
            title="آپارتمان تست",
            location="SRID=4326;POINT(51.4000 35.7000)",
        )
        demand = ClientDemand(
            client_name="مشتری تست",
            target_area=(
                "SRID=4326;POLYGON((51.30 35.60, 51.50 35.60, "
                "51.50 35.80, 51.30 35.80, 51.30 35.60))"
            ),
        )
        session.add(prop)
        session.add(demand)
        await session.commit()
        await session.refresh(prop)
        await session.refresh(demand)

        stmt = select(func.ST_Contains(demand.target_area, prop.location)).where(
            Property.id == prop.id
        )
        inside = (await session.execute(stmt)).first()
        assert inside is not None
        assert inside[0] is True

        # Clean up.
        await session.delete(prop)
        await session.delete(demand)
        await session.commit()


async def test_st_distance_between_points(db_ready) -> None:
    async with AsyncSessionLocal() as session:
        distance = (
            await session.execute(
                text(
                    "SELECT ST_Distance("
                    "ST_GeomFromText('POINT(51.4 35.7)', 4326)::geography, "
                    "ST_GeomFromText('POINT(51.5 35.7)', 4326)::geography)"
                )
            )
        ).scalar()
        assert distance is not None
        assert 8000 < distance < 10000  # roughly ~9 km at this latitude


async def test_license_service_persists_status(tmp_path: Path, db_ready) -> None:
    from sqlalchemy import delete

    # This service owns a singleton row; start from a clean slate.
    async with AsyncSessionLocal() as session:
        await session.execute(delete(NodeLicense))
        await session.commit()

    private_pem, public_pem = generate_keypair(key_size=2048)
    license_file = tmp_path / "node.lic"
    public_file = tmp_path / "license_public.pem"
    public_file.write_bytes(public_pem)

    settings = Settings(
        license_file=license_file,
        license_public_key_file=public_file,
        machine_fingerprint_override="integration-test-machine",
        offline_grace_days=14,
    )
    manager = license_service.build_manager(settings)
    now = int(time.time())
    payload = LicensePayload(
        license_id="AVG-INT-1",
        agency_name="املاک یکپارچه",
        machine_fingerprint_hash=manager.machine_fingerprint_hash(),
        max_concurrent_users=12,
        issued_at=now,
        expires_at=now + 30 * 86400,
        features=["MLS"],
    )
    license_file.write_text(encode_license(payload, private_pem), encoding="utf-8")

    async with AsyncSessionLocal() as session:
        row = await license_service.sync_license_from_disk(session, settings)
        assert isinstance(row, NodeLicense)
        assert row.agency_name == "املاک یکپارچه"
        assert row.max_concurrent_users == 12
        assert row.feature_list() == ["MLS"]
        assert row.status.value == "GRACE_PERIOD"
        assert row.is_usable

        # Heartbeat extends the grace window and marks ACTIVE.
        row2 = await license_service.record_heartbeat(session, settings=settings)
        assert row2.status.value == "ACTIVE"
        assert row2.offline_grace_deadline is not None

        # Cleanup.
        await session.execute(delete(NodeLicense))
        await session.commit()


# ---------------------------------------------------------------------------
# Source filter
# ---------------------------------------------------------------------------
async def test_source_filter_expands_legacy_labels(db_ready) -> None:
    """`?source=DIVAR` must match rows stored under the pre-rename labels.

    Every crawled row on this node is DIVAR_SCRAPER, and none are DIVAR, so a
    naive equality filter would report an empty inventory on a node whose every
    card is labelled "دیوار".
    """
    from app.api.v1.endpoints.properties import _SOURCE_EQUIVALENTS
    from app.models.enums import PropertySource

    equivalents = _SOURCE_EQUIVALENTS[PropertySource.DIVAR]
    assert PropertySource.DIVAR_KENAR in equivalents
    assert PropertySource.DIVAR_SCRAPER in equivalents
    assert PropertySource.INTERNAL_AGENCY not in equivalents

    async with AsyncSessionLocal() as session:
        legacy = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Property)
                    .where(Property.source == PropertySource.DIVAR_SCRAPER)
                )
            ).scalar()
            or 0
        )
        canonical = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Property)
                    .where(Property.source == PropertySource.DIVAR)
                )
            ).scalar()
            or 0
        )
        # What the filter actually expands to.
        matched = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Property)
                    .where(Property.source.in_(equivalents))
                )
            ).scalar()
            or 0
        )

    assert matched == legacy + canonical


async def test_source_buckets_partition_every_source(db_ready) -> None:
    """Each stored source falls in exactly one bucket, and every member is covered."""
    from app.api.v1.endpoints.properties import _SOURCE_EQUIVALENTS
    from app.models.enums import PropertySource

    covered = [member for members in _SOURCE_EQUIVALENTS.values() for member in members]
    assert sorted(map(str, covered)) == sorted(map(str, PropertySource))
    assert len(covered) == len(set(covered)), "a source landed in two buckets"

    async with AsyncSessionLocal() as session:
        stored = {
            row for row in (await session.execute(select(Property.source))).scalars().all()
        }
    for source in stored:
        assert any(source in members for members in _SOURCE_EQUIVALENTS.values())
