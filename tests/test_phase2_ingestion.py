"""Phase 2 ingestion tests: parser, dedupe, PII vault, pipeline (SQLite)."""

from __future__ import annotations

import asyncio
import contextlib
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.core.crypto import PiiCipher  # noqa: E402
from app.models.enums import (  # noqa: E402
    DealType,
    PropertySource,
    PropertyStatus,
    PropertyType,
    ScrapeJobKind,
    ScrapeJobTrigger,
)
from app.models.property import Property  # noqa: E402
from app.models.property_owner_pii import PropertyOwnerPII  # noqa: E402
from app.models.scrape_job import ScrapeJob  # noqa: E402
from app.services import scraper_service  # noqa: E402
from app.services.events import NEW_PROPERTY_INGESTED, event_bus  # noqa: E402
from app.services.ingestion.deduplicator import compute_content_hash, find_duplicate  # noqa: E402
from app.services.ingestion.pipeline import process_detail, run_search_job, store_owner_pii  # noqa: E402
from app.services.scraper.cache import TokenCache  # noqa: E402
from app.services.scraper.divar_client import DivarClient, ScraperBlockedError  # noqa: E402
from app.services.scraper.parser import (  # noqa: E402
    DivarListingDetail,
    is_transferable_category,
    map_category,
    parse_bool,
    parse_float,
    parse_int,
    parse_post_detail,
    parse_price,
    parse_search_response,
)
from app.services.scraper.phone_extractor import PhoneExtractor, parse_phone  # noqa: E402

# Shorthand aliases used across the taxonomy assertions below.
_P = PropertyType
_D = DealType

TEST_SETTINGS = Settings(
    database_url="sqlite+aiosqlite://",
    scraper_enabled=True,
    scraper_pace_min_seconds=0.0,
    scraper_pace_max_seconds=0.0,
    scraper_base_backoff_seconds=1.0,
    scraper_cities="tehran",
    scraper_categories="apartment-sell",
)


def _cipher() -> PiiCipher:
    return PiiCipher(PiiCipher.generate_key())


def _run(coro):
    """Run a coroutine on a dedicated loop (resilient to closed/absent loops).

    Other test modules (pytest-asyncio) may have created and closed the
    main-thread loop already — ``asyncio.get_event_loop()`` then raises.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


_SHARED_SQLITE_ENGINE = None
_SHARED_DB_FILE = None
_SHARED_SCHEMA_DONE = False


def _sqlite_safe_metadata() -> sa.MetaData:
    """Copy the model metadata with PG-only types retyped for SQLite.

    GeoAlchemy2 emits PostGIS-only DDL (and a ``RecoverGeometryColumn``
    reflection function) that SQLite does not provide; PG enums/arrays/JSONB
    likewise have no SQLite equivalent.
    """
    from sqlalchemy import JSON
    from sqlalchemy.dialects.postgresql import ARRAY as PgArray
    from sqlalchemy.dialects.postgresql import ENUM as PgEnum
    from sqlalchemy.types import String

    own = sa.MetaData()
    for table in SQLModel.metadata.tables.values():
        table.to_metadata(own)
    for table in own.tables.values():
        for col in table.columns:
            if isinstance(col.type, Geometry):
                col.type = String()
            elif isinstance(col.type, PgEnum):
                col.type = String(64)
            elif isinstance(col.type, PgArray):
                col.type = JSON()
    return own


def _register_spatial_udfs(engine) -> None:
    """Register the GeomFromEWKT/AsEWKB UDFs GeoAlchemy2 compiles into DML."""

    @sa.event.listens_for(engine.sync_engine, "connect")
    def _udfs(dbapi_conn, _record) -> None:
        dbapi_conn.create_function("GeomFromEWKT", -1, _sqlite_geom_from_ewkt)
        dbapi_conn.create_function("AsEWKB", 1, _sqlite_as_ewkb)


async def _dispose_engine(sess, engine) -> None:
    await sess.close()
    await engine.dispose()


def _shared_engine():
    global _SHARED_SQLITE_ENGINE, _SHARED_DB_FILE
    if _SHARED_SQLITE_ENGINE is None:
        import atexit
        import os
        import tempfile

        from sqlalchemy import event
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        # A temp FILE database (not ":memory:"): pooled connections can be
        # dropped and re-created between tests — an in-memory DB would silently
        # lose the schema on reconnect while _SHARED_SCHEMA_DONE stays True.
        fd, _SHARED_DB_FILE = tempfile.mkstemp(prefix="avg-phase2-", suffix=".sqlite")
        os.close(fd)
        atexit.register(_cleanup_shared_db)
        _SHARED_SQLITE_ENGINE = create_async_engine(f"sqlite+aiosqlite:///{_SHARED_DB_FILE}")
        # GeoAlchemy2 compiles geometry columns into ST_GeomFromEWKT/ST_AsEWKB
        # calls (renamed GeomFromEWKT/AsEWKB on the sqlite dialect). SQLite has
        # no such functions, so we emulate them with plain Python UDFs: writes
        # store EWKT text, reads convert it back to hex EWKB for WKBElement.
        @event.listens_for(_SHARED_SQLITE_ENGINE.sync_engine, "connect")
        def _register_spatial_udfs(dbapi_conn, _record) -> None:
            dbapi_conn.create_function("GeomFromEWKT", -1, _sqlite_geom_from_ewkt)
            dbapi_conn.create_function("AsEWKB", 1, _sqlite_as_ewkb)
    return _SHARED_SQLITE_ENGINE


def _cleanup_shared_db() -> None:
    import os

    if _SHARED_DB_FILE and os.path.exists(_SHARED_DB_FILE):
        try:
            os.unlink(_SHARED_DB_FILE)
        except OSError:  # pragma: no cover - best effort cleanup
            pass


def _sqlite_geom_from_ewkt(*args):
    """Store the bind value as-is (EWKT text or NULL)."""
    return args[0] if args else None


def _sqlite_as_ewkb(value):
    """Convert stored EWKT/WKT text into hex EWKB (SpatiaLite-style)."""
    if value is None:
        return None
    import struct as _struct

    text = str(value)
    srid = 4326
    if text[:5].upper() == "SRID=":
        head, text = text.split(";", 1)
        srid = int(head.split("=", 1)[1])
    inner = text[text.find("(") + 1 : text.find(")")]
    parts = inner.replace(",", " ").split()
    x, y = float(parts[0]), float(parts[1])
    # Little-endian EWKB point with SRID flag set.
    return _struct.pack("<BIIdd", 1, 0x20000000 | 1, srid, x, y).hex()


def _make_session() -> AsyncSession:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlalchemy import JSON, MetaData, text
    from sqlalchemy.types import String
    from sqlalchemy.dialects.postgresql import ARRAY as PgArray
    from sqlalchemy.dialects.postgresql import ENUM as PgEnum
    from geoalchemy2 import Geometry
    global _SHARED_SCHEMA_DONE
    factory = async_sessionmaker(
        bind=_shared_engine(), class_=AsyncSession, expire_on_commit=False
    )
    async def _init() -> AsyncSession:
        global _SHARED_SCHEMA_DONE
        session = factory()
        if not _SHARED_SCHEMA_DONE:
            def _create(conn) -> None:
                # Rebuild a sqlite-safe schema: Geometry -> TEXT, PG enums -> TEXT,
                # PG arrays -> JSON. Geometry columns must be manually re-typed
                # *before* create_all because the DDL compiler dispatches on the
                # original GeoAlchemy type.
                own = MetaData()
                for table in SQLModel.metadata.tables.values():
                    table.to_metadata(own)
                geo_cols: list[tuple[str, str]] = []
                for own_table in own.tables.values():
                    for col in own_table.columns:
                        if isinstance(col.type, Geometry):
                            geo_cols.append((own_table.name, col.name))
                            col.type = String()
                        elif isinstance(col.type, (PgEnum,)):
                            col.type = String(64)
                        elif isinstance(col.type, (PgArray,)):
                            col.type = JSON()
                own.create_all(conn)
                # Defensive: if any geometry DDL slipped through as a no-op (sqlite
                # has no GeomFromEWKT), ensure those columns exist as TEXT.
                existing = {
                    r[0]
                    for r in conn.execute(
                        text("SELECT name FROM sqlite_master WHERE type='table'")
                    ).fetchall()
                }
                for table_name, col_name in geo_cols:
                    if table_name not in existing:
                        continue
                    cols = {
                        r[1]
                        for r in conn.execute(
                            text(f'PRAGMA table_info(\"{table_name}\")')
                        ).fetchall()
                    }
                    if col_name not in cols:
                        conn.execute(text(f'ALTER TABLE \"{table_name}\" ADD COLUMN \"{col_name}\" TEXT'))
            conn = await session.connection()
            await conn.run_sync(_create)
            await session.commit()
            _SHARED_SCHEMA_DONE = True
        return session
    return _run(_init())


@pytest.fixture()
def session() -> AsyncSession:
    return _make_session()

def test_parse_price_persian_digits() -> None:
    assert parse_price("۹٬۵۰۰٬۰۰۰٬۰۰۰ تومان") == 9_500_000_000
    assert parse_price("توافقی") is None
    assert parse_price(None) is None


def test_parse_int_float_bool() -> None:
    assert parse_int("۱۲۳ متر") == 123
    assert parse_float("۸۵.۵") == 85.5
    assert parse_bool("دارد") is True
    assert parse_bool("ندارد") is False


def test_map_category_known_and_fallback() -> None:
    from app.models.enums import DealType as _D
    from app.models.enums import PropertyType as _P
    ptype, deal = map_category("apartment-sell")
    assert ptype == _P.APARTMENT and deal == _D.SALE
    ptype, deal = map_category("villa-rent")
    assert ptype == _P.VILLA and deal == _D.RENT


def test_parse_search_response_collapses_duplicates() -> None:
    payload = {"list_widgets": [
        {"data": {"token": "QX123", "title": "t1", "city": "tehran", "district": "x"}},
        {"data": {"token": "QX123", "title": "dup"}},
    ]}
    summaries = parse_search_response(payload)
    assert len(summaries) == 1
    assert summaries[0].token == "QX123"


def test_parse_post_detail_widgets() -> None:
    payload = {
        "title": "apt 120", "city": "tehran", "district": "ponak",
        "category": "apartment-sell",
        "widgets": [
            {"title": "متراژ", "value": "۱۲۰"},
            {"title": "تعداد اتاق", "value": "۲"},
            {"title": "قیمت کل", "value": "۸٬۰۰۰٬۰۰۰٬۰۰۰"},
            {"title": "آسانسور", "value": "دارد"},
        ],
        "map": {"latitude": 35.7, "longitude": 51.4},
        "images": ["https://img/1.jpg"],
    }
    detail = parse_post_detail(payload, "QX999")
    assert detail.area == 120.0
    assert detail.rooms == 2
    assert detail.total_price == 8_000_000_000
    assert detail.has_elevator is True
    assert detail.latitude == 35.7


# ---------------------------------------------------------------------------
#  Regression tests against the documented Divar reference schemas.
#  Each pins a field that the first Phase-2 parser silently dropped.
# ---------------------------------------------------------------------------

# Verbatim shape from docs/divar_taxonomy.md ("Post Detail Schema").
DIVAR_DETAIL_PAYLOAD = {
    "token": "gZ1234AB",
    "category": "apartment-sell",
    "city": "tehran",
    "district": "saadat-abad",
    "title": "آپارتمان ۱۱۰ متری سالن پرده‌خور",
    "description": "توضیحات کامل آگهی",
    "contact": {
        "phone": "09121234567",
        "business_type": "real-estate-business",
        "agent_name": "املاک نام‌آوران",
        "slug": "amlak-namavaran",
    },
    "widgets": {
        "list_data": [
            {"title": "متراژ", "value": "۱۱۰"},
            {"title": "ساخت", "value": "۱۴۰۱"},
            {"title": "اتاق", "value": "۲"},
            {"title": "طبقه", "value": "۳ از ۵"},
            {"title": "تعداد واحد در طبقه", "value": "۲"},
        ],
        "amenities": [
            {"title": "آسانسور", "available": True},
            {"title": "پارکینگ", "available": True},
            {"title": "انباری", "available": False},
            {"title": "بالکن", "available": True},
        ],
        "financial": {
            "total_price": 12_500_000_000,
            "price_per_meter": 113_636_000,
            "deposit": None,
            "monthly_rent": None,
            "convertible": False,
        },
        "location": {"latitude": 35.7812, "longitude": 51.3725, "radius": 150},
        "images": [
            "https://s100.divarcdn.com/static/photo/post/xxx/1.jpg",
            "https://s100.divarcdn.com/static/photo/post/xxx/2.jpg",
        ],
    },
}


def test_detail_financial_block_is_used() -> None:
    """``widgets.financial`` carries clean numerics; they win over label text."""
    d = parse_post_detail(DIVAR_DETAIL_PAYLOAD, "gZ1234AB")
    assert d.total_price == 12_500_000_000
    assert d.price_per_meter == 113_636_000
    assert d.price_is_convertible is False


def test_detail_amenity_rows_are_parsed() -> None:
    """``{title, available}`` rows are not label/value pairs."""
    d = parse_post_detail(DIVAR_DETAIL_PAYLOAD, "gZ1234AB")
    assert d.has_elevator is True
    assert d.has_parking is True
    assert d.has_storage is False
    assert d.has_balcony is True


def test_detail_top_level_district_is_kept() -> None:
    """``district`` is a top-level key, not a محله label row."""
    d = parse_post_detail(DIVAR_DETAIL_PAYLOAD, "gZ1234AB")
    assert d.district == "saadat-abad"
    assert d.neighborhood == "saadat-abad"


def test_detail_contact_phone_feeds_pii_vault() -> None:
    """An inline contact.phone must not be dropped when no extractor ran."""
    d = parse_post_detail(DIVAR_DETAIL_PAYLOAD, "gZ1234AB")
    assert d.phone == "09121234567"
    assert d.business_type == "real-estate-business"
    assert d.agent_name == "املاک نام‌آوران"


def test_detail_explicit_phone_argument_wins() -> None:
    d = parse_post_detail(DIVAR_DETAIL_PAYLOAD, "gZ1234AB", phone="09129999999")
    assert d.phone == "09129999999"


def test_detail_floor_range_and_specs() -> None:
    """``طبقه: "۳ از ۵"`` must yield both floor and building height."""
    d = parse_post_detail(DIVAR_DETAIL_PAYLOAD, "gZ1234AB")
    assert d.floor == 3
    assert d.total_floors == 5
    assert d.units_per_floor == 2
    assert d.year_built == 1401
    assert d.area == 110.0
    assert d.rooms == 2
    assert d.coordinate_radius == 150
    assert len(d.images) == 2


def test_detail_rent_financial_block() -> None:
    payload = {
        "category": "apartment-rent",
        "city": "tehran",
        "district": "saadat-abad",
        "widgets": {
            "financial": {
                "total_price": None,
                "deposit": 500_000_000,
                "monthly_rent": 15_000_000,
            },
            "list_data": [{"title": "متراژ", "value": "۹۰"}],
        },
    }
    d = parse_post_detail(payload, "QX-RENT")
    assert d.deal_type == _D.RENT
    assert d.deposit == 500_000_000
    assert d.monthly_rent == 15_000_000
    assert d.total_price is None


def test_detail_deposit_only_lease_is_full_mortgage() -> None:
    """A lease quoted as a deposit with no monthly rent is «رهن کامل».

    Divar never sends a FULL_MORTGAGE category slug — it only leaves the rent
    field empty — so the parser must read that off the numbers, otherwise every
    deposit-only lease is stored as RENT and the desk's «رهن کامل» filter comes
    back empty even when the inventory holds such units.
    """
    payload = {
        "category": "apartment-rent",
        "city": "tehran",
        "district": "vanak",
        "widgets": {
            "financial": {
                "total_price": None,
                "deposit": 800_000_000,
                "monthly_rent": None,
            },
            "list_data": [{"title": "متراژ", "value": "۹۰"}],
        },
    }
    d = parse_post_detail(payload, "QX-FULL")
    assert d.deal_type == _D.FULL_MORTGAGE
    assert d.deposit == 800_000_000
    assert d.monthly_rent is None
    assert d.total_price is None


def test_detail_convertible_price_is_flagged() -> None:
    payload = {
        "category": "apartment-sell",
        "city": "tehran",
        "widgets": {"list_data": [{"title": "قیمت کل", "value": "توافقی"}]},
    }
    d = parse_post_detail(payload, "QX-NEG")
    assert d.price_is_convertible is True
    assert d.total_price is None


def test_search_card_three_line_text_and_flags() -> None:
    """Post-card fields feed the pipeline's district/price and dedupe."""
    payload = {
        "list_widgets": [
            {
                "data": {
                    "token": "QX-CARD",
                    "title": "آپارتمان ۱۱۰ متری دو خوابه فول",
                    "top_description_text": "دقایقی پیش در سعادت‌آباد",
                    "middle_description_text": "۱۱۰ متر • ۲ خوابه • ساخت ۱۴۰۱",
                    "bottom_description_text": "۱۲٬۵۰۰٬۰۰۰٬۰۰۰ تومان",
                    "image_url": "https://s100.divarcdn.com/x.jpg",
                    "district": "سعادت‌آباد",
                    "city": "tehran",
                    "has_chat": True,
                    "red_text": "فوری",
                }
            }
        ]
    }
    s = parse_search_response(payload)[0]
    assert s.top_description_text == "دقایقی پیش در سعادت‌آباد"
    assert s.middle_description_text == "۱۱۰ متر • ۲ خوابه • ساخت ۱۴۰۱"
    assert s.bottom_description_text == "۱۲٬۵۰۰٬۰۰۰٬۰۰۰ تومان"
    assert s.has_chat is True
    assert s.red_text == "فوری"
    assert s.image_url == "https://s100.divarcdn.com/x.jpg"
    # bottom_description_text is the price line, so it must feed price_hint.
    assert "۱۲٬۵۰۰" in s.price_hint


def test_taxonomy_web_and_api_slugs_map_identically() -> None:
    """Both naming layers of Divar's taxonomy must classify the same way."""
    pairs = [
        (("buy-apartment", "apartment-sell"), _P.APARTMENT, _D.SALE),
        (("rent-apartment", "apartment-rent"), _P.APARTMENT, _D.RENT),
        (("buy-villa", "house-villa-sell"), _P.VILLA, _D.SALE),
        (("rent-villa", "house-villa-rent"), _P.VILLA, _D.RENT),
        (("buy-old-house", "plot-old"), _P.LAND, _D.SALE),
        (("buy-office", "office-sell"), _P.OFFICE, _D.SALE),
        (("rent-store", "store-rent"), _P.STORE, _D.RENT),
        (
            ("buy-industrial-agricultural-property", "industrial-sell"),
            _P.INDUSTRIAL,
            _D.SALE,
        ),
        (
            ("rent-industrial-agricultural-property", "industrial-rent"),
            _P.INDUSTRIAL,
            _D.RENT,
        ),
        (("suite-apartment", "temporary-rent"), _P.SUITE, _D.RENT),
    ]
    for (web_slug, api_slug), expected_type, expected_deal in pairs:
        assert map_category(web_slug) == (expected_type, expected_deal), web_slug
        assert map_category(api_slug) == (expected_type, expected_deal), api_slug


def test_taxonomy_unknown_slug_degrades_safely() -> None:
    """An unseen slug must not silently type a plot as an apartment."""
    assert map_category("buy-old-house")[0] == _P.LAND
    assert map_category("brand-new-category-1404")[0] == _P.APARTMENT
    assert map_category("rent-brand-new-category")[1] == _D.RENT


def test_non_transferable_categories_flagged() -> None:
    assert is_transferable_category("apartment-sell") is True
    assert is_transferable_category("construction-partnership") is False
    assert is_transferable_category("pre-sell-home") is False


def test_sanitizer_maps_new_detail_fields() -> None:
    """Newly parsed fields must actually reach the Property row."""
    from app.services.ingestion.sanitizer import build_property_fields

    detail = parse_post_detail(DIVAR_DETAIL_PAYLOAD, "gZ1234AB")
    fields = build_property_fields(detail, content_hash="h")
    assert fields["price_per_meter"] == 113_636_000
    assert fields["units_per_floor"] == 2
    assert fields["has_balcony"] is True
    assert fields["has_elevator"] is True
    assert fields["neighborhood"] == "saadat-abad"
    assert fields["location"] == "SRID=4326;POINT(51.3725 35.7812)"


# ---------------------------------------------------------------------------
#  City registry / API-layer id resolution (web slug -> numeric city_id).
# ---------------------------------------------------------------------------


def test_city_registry_resolves_slugs_and_aliases() -> None:
    from app.services.scraper import cities

    assert cities.resolve_city_id("tehran") == cities.get_city("tehran").city_id
    assert cities.normalize_city_slug("  Tehran ") == "tehran"
    # Persian labels typed into SCRAPER_CITIES must resolve.
    assert cities.normalize_city_slug("شیراز") == "shiraz"
    assert cities.resolve_city_id("شیراز") == cities.resolve_city_id("shiraz")


def test_city_registry_rejects_unknown_city() -> None:
    from app.services.scraper import cities

    with pytest.raises(cities.UnknownCityError) as exc:
        cities.resolve_city_id("atlantis")
    assert "tehran" in str(exc.value)


def test_district_ids_resolve_per_city() -> None:
    from app.services.scraper import cities

    ids = cities.resolve_district_ids("tehran", ["tehran-saat-abad"])
    assert ids == [cities.get_city("tehran").districts["tehran-saat-abad"]]
    # Duplicates collapse.
    assert cities.resolve_district_ids("tehran", ["tehran-saat-abad"] * 2) == ids


def test_district_rejects_unknown_and_wrong_city() -> None:
    from app.services.scraper import cities

    with pytest.raises(cities.UnknownDistrictError):
        cities.resolve_district_ids("tehran", ["atlantis-quarter"])
    # A district registered for Tehran is unknown for Shiraz.
    with pytest.raises(cities.UnknownDistrictError):
        cities.resolve_district_ids("shiraz", ["tehran-saat-abad"])


def test_search_payload_uses_numeric_city_id() -> None:
    """The API layer must receive ids, not web slugs.

    Divar's RPC bridge types ``city_ids`` as TYPE_STRING, so the numeric id is
    serialised as a string on the wire while still being a *number* from
    ``cities`` — sending the bare int is rejected with
    "city_ids[0]: invalid value 1 for type TYPE_STRING".
    """
    from app.services.scraper import cities

    client = DivarClient(settings=TEST_SETTINGS)
    body = client._search_payload("tehran", "apartment-sell", 2)
    assert body["city_ids"] == [str(cities.resolve_city_id("tehran"))]
    assert "tehran" not in body["city_ids"]
    assert body["pagination_data"]["page"] == 2
    # form_data wraps each filter in a "data" envelope, mirroring Divar's
    # protobuf JSON shape.
    assert body["search_data"]["form_data"]["data"]["category"] == {
        "str": {"value": "apartment-sell"}
    }


def test_search_payload_adds_district_filter() -> None:
    from app.services.scraper import cities

    client = DivarClient(settings=TEST_SETTINGS)
    body = client._search_payload(
        "tehran", "apartment-sell", 1, districts=["tehran-saat-abad"]
    )
    # Unlike `city_ids`, the district filter keeps native ints: only the top
    # level city id goes through the TYPE_STRING bridge.
    expected = cities.resolve_district_ids("tehran", ["tehran-saat-abad"])
    assert body["search_data"]["form_data"]["data"]["district"] == {
        "int": {"value": list(expected)}
    }
    # No districts -> no district filter key at all.
    plain = client._search_payload("tehran", "apartment-sell", 1)
    assert "district" not in plain["search_data"]["form_data"]["data"]


def test_search_payload_rejects_unknown_city_before_request() -> None:
    from app.services.scraper import cities

    client = DivarClient(settings=TEST_SETTINGS)
    with pytest.raises(cities.UnknownCityError):
        client._search_payload("atlantis", "apartment-sell", 1)


def test_registry_provenance_is_explicit() -> None:
    """Unverified ids must be discoverable, not silently trusted."""
    from app.services.scraper import cities

    assert len(cities.unverified_cities()) == len(cities.CITIES)
    assert "tehran" in cities.known_city_slugs()
    # Persian labels must not collide with a different city.
    assert cities.get_city("urmia").persian == "ارومیه"


def test_job_create_persists_districts(session) -> None:
    from app.schemas.scraper import ScrapeJobCreate
    from app.services import scraper_service

    async def _inner() -> None:
        payload = ScrapeJobCreate(
            source="sheypoor",
            city="tehran",
            category="houses-apartments-for-sale",
            districts=[" tehran-saat-abad ", ""],
        )
        # Whitespace-only entries are dropped by the schema validator.
        assert payload.districts == ["tehran-saat-abad"]
        job = await scraper_service.create_job(session, payload, settings=_verified_job_settings())
        assert job.params["districts"] == ["tehran-saat-abad"]
    _run(_inner())


def _verified_job_settings(**overrides) -> Settings:
    base = {
        "database_url": "sqlite+aiosqlite://",
        "scraper_enabled": True,
        "scraper_cities": "tehran,mashhad",
        "scraper_categories": "apartment-sell",
        "scraper_sources": "delta,sheypoor",
        "scraper_pace_min_seconds": 0.0,
        "scraper_pace_max_seconds": 0.0,
    }
    base.update(overrides)
    return Settings(**base)


def _sched_settings(**overrides) -> "Settings":
    base = {
        "database_url": "sqlite+aiosqlite://",
        "scraper_enabled": True,
        "scraper_scheduler_enabled": True,
        "scraper_cities": "tehran,mashhad",
        "scraper_categories": "apartment-sell",
        "scraper_schedule_interval_minutes": 60,
        "scraper_schedule_jitter_seconds": 90,
        "scraper_schedule_initial_delay_seconds": 0,
        "scraper_schedule_max_pages": 2,
    }
    base.update(overrides)
    return Settings(**base)


@contextlib.contextmanager
def _patched_scheduler(session_ok: bool = True, lock_acquired: bool = True,
                       launched: list | None = None) -> list:
    """Patch the scheduler's DB guards so tests can drive ``tick()`` offline."""
    from app.services import scraper_scheduler as sched

    real_license = sched._license_usable
    real_lock = sched._scheduler_lock
    real_launch = sched.scraper_service.launch_job_background
    real_trigger = sched.scraper_service.trigger_with_trigger
    captured: list = []

    async def _allow(_s, _st):
        return session_ok

    @contextlib.asynccontextmanager
    async def _lock(_s):
        yield lock_acquired

    async def _offline_trigger(session, payload, **kwargs):
        kwargs.pop("wait", None)
        kwargs["trigger"] = ScrapeJobTrigger.SCHEDULED
        return await sched.scraper_service.create_job(session, payload, **kwargs)

    def _launch(job_id, _params):
        captured.append(job_id)
        return None

    sched._license_usable = _allow
    sched._scheduler_lock = _lock
    sched.scraper_service.trigger_with_trigger = _offline_trigger
    sched.scraper_service.launch_job_background = _launch
    try:
        yield captured if launched is None else launched
    finally:
        sched._license_usable = real_license
        sched._scheduler_lock = real_lock
        sched.scraper_service.launch_job_background = real_launch
        sched.scraper_service.trigger_with_trigger = real_trigger


def _sqlite_sessionmaker():
    """An ``async_sessionmaker`` bound to the shared test DB."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlmodel.ext.asyncio.session import AsyncSession

    return async_sessionmaker(
        bind=_shared_engine(), class_=AsyncSession, expire_on_commit=False
    )


def test_scheduler_inert_when_disabled() -> None:
    """Default posture: no autonomous crawling unless explicitly enabled."""
    from app.services.scraper_scheduler import ScrapeScheduler

    sch = ScrapeScheduler(_sched_settings(scraper_scheduler_enabled=False))
    assert _run(sch.tick()) == []

    sch2 = ScrapeScheduler(_sched_settings(scraper_enabled=False))
    assert _run(sch2.tick()) == []


def test_scheduler_interval_has_jitter_and_floor() -> None:
    from app.services.scraper_scheduler import ScrapeScheduler

    sch = ScrapeScheduler(_sched_settings())
    intervals = {sch.interval_seconds() for _ in range(20)}
    assert len(intervals) > 1, "identical intervals would sync every worker"
    assert all(3600 <= i <= 3690 for i in intervals)
    # Zero interval is floored to 1 minute instead of busy-looping.
    fast = ScrapeScheduler(_sched_settings(scraper_schedule_interval_minutes=0))
    assert fast.interval_seconds() >= 60


def test_scheduler_skips_unlicensed_node() -> None:
    """No usable license -> no jobs, mirroring the HTTP LicenseGuard."""
    from app.services.scraper_scheduler import ScrapeScheduler

    sch = ScrapeScheduler(_sched_settings())
    with _patched_scheduler(session_ok=False):
        assert _run(sch.tick()) == []


def test_scheduler_respects_advisory_lock() -> None:
    """A second worker holding the lock must schedule nothing."""
    from app.services.scraper_scheduler import ScrapeScheduler

    sch = ScrapeScheduler(_sched_settings())
    with _patched_scheduler(lock_acquired=False):
        assert _run(sch.tick()) == []


# ---------------------------------------------------------------------------
#  Dashboard statistics (Phase 2b).
# ---------------------------------------------------------------------------


@pytest.fixture()
def stats_session():
    """A session on an isolated DB so statistics never see other tests' jobs.

    ``collect_stats`` aggregates the whole ``scrape_job`` table, so it must not
    share the module-wide DB where other tests have already created jobs.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool
    from sqlmodel.ext.asyncio.session import AsyncSession

    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    _register_spatial_udfs(engine)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    own = _sqlite_safe_metadata()

    async def _create() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(own.create_all)

    _run(_create())
    sess = factory()
    try:
        yield sess
    finally:
        _run(_dispose_engine(sess, engine))


def _mk_job(session, **kw) -> "ScrapeJob":
    """Insert a fully-populated ScrapeJob for statistics tests."""
    from app.models.base import utcnow
    from app.models.enums import ScrapeJobStatus as _St

    defaults = dict(
        kind=ScrapeJobKind.SEARCH,
        status=_St.COMPLETED,
        trigger=ScrapeJobTrigger.SCHEDULED,
        city="tehran",
        category="apartment-sell",
        params={},
        pages_scraped=1,
        items_found=10,
        items_new=6,
        items_duplicate=3,
        items_failed=1,
        started_at=utcnow(),
        finished_at=utcnow(),
    )
    defaults.update(kw)
    job = ScrapeJob(**defaults)
    session.add(job)
    return job


def test_collect_stats_totals_and_rates(stats_session) -> None:
    from app.services import scraper_stats

    async def _inner() -> None:
        _mk_job(stats_session)
        _mk_job(stats_session, items_found=10, items_new=2, items_duplicate=7, items_failed=1)
        await stats_session.commit()

        stats = await scraper_stats.collect_stats(stats_session, hours=24)
        assert stats["window_hours"] == 24
        assert stats["jobs"]["total"] == 2
        assert stats["jobs"]["completed"] == 2
        assert stats["items"]["found"] == 20
        assert stats["items"]["new"] == 8
        assert stats["items"]["duplicate"] == 10
        # 10/20 duplicates, 2/20 failures
        assert stats["rates"]["duplicate"] == 0.5
        assert stats["rates"]["failure"] == 0.1
        # Rates always sum to 1 when every item is accounted for.
        assert round(sum(stats["rates"].values()), 4) == 1.0

    _run(_inner())


def test_collect_stats_empty_is_safe(stats_session) -> None:
    """No jobs -> zeros, never a ZeroDivisionError."""
    from app.services import scraper_stats

    async def _inner() -> None:
        stats = await scraper_stats.collect_stats(stats_session, hours=24)
        assert stats["jobs"]["total"] == 0
        assert stats["rates"] == {"new": 0.0, "duplicate": 0.0, "failure": 0.0}

    _run(_inner())


def test_collect_stats_respects_window(stats_session) -> None:
    from datetime import timedelta

    from app.models.base import utcnow
    from app.services import scraper_stats

    async def _inner() -> None:
        old = utcnow() - timedelta(days=3)
        _mk_job(stats_session, created_at=old, started_at=old, finished_at=old)
        _mk_job(stats_session)
        await stats_session.commit()

        assert (await scraper_stats.collect_stats(stats_session, hours=24))["jobs"]["total"] == 1
        assert (await scraper_stats.collect_stats(stats_session, hours=168))["jobs"]["total"] == 2

    _run(_inner())


def test_collect_city_health_groups_by_pair(stats_session) -> None:
    from app.models.base import utcnow
    from app.models.enums import ScrapeJobStatus as _St
    from app.services import scraper_stats

    async def _inner() -> None:
        # Tehran: 2 successful runs, 20 items found, 10 of them duplicates.
        _mk_job(stats_session, items_found=10, items_new=10, items_duplicate=0,
                items_failed=0)
        _mk_job(stats_session, items_found=10, items_new=0, items_duplicate=10,
                items_failed=0)
        # Shiraz: one run that FAILED. ``run_search_job``'s finally block always
        # stamps finished_at, so a failure still "finishes" — the health flag
        # must rely on status, not on the timestamp.
        failed_at = utcnow()
        _mk_job(stats_session, city="shiraz", status=_St.FAILED, items_failed=10,
                items_found=10, items_new=0, items_duplicate=0,
                error="HTTP 403 for https://api.divar.ir/v8/postlist/w/search",
                finished_at=failed_at)
        await stats_session.commit()

        health = {h["city"]: h for h in await scraper_stats.collect_city_health(stats_session)}
        assert set(health) == {"tehran", "shiraz"}
        # Tehran: 20 found, 10 duplicate -> 0.5, and it finished cleanly.
        assert health["tehran"]["jobs"] == 2
        assert health["tehran"]["runs_completed"] == 2
        assert health["tehran"]["runs_failed"] == 0
        assert health["tehran"]["duplicate_rate"] == 0.5
        assert health["tehran"]["healthy"] is True
        # Shiraz's only run FAILED. It has finished_at set (it finished by
        # failing), which must NOT be mistaken for a healthy scrape.
        assert health["shiraz"]["runs_completed"] == 0
        assert health["shiraz"]["runs_failed"] == 1
        assert health["shiraz"]["last_finished_at"] is not None
        assert health["shiraz"]["healthy"] is False
        assert health["shiraz"]["failure_rate"] == 1.0

    _run(_inner())


def test_find_stuck_pairs_and_recent_errors(stats_session) -> None:
    from datetime import timedelta

    from app.models.base import utcnow
    from app.models.enums import ScrapeJobStatus as _St
    from app.services import scraper_stats

    async def _inner() -> None:
        stuck_job = _mk_job(stats_session, status=_St.RUNNING, finished_at=None,
                            started_at=utcnow() - timedelta(minutes=90))
        _mk_job(stats_session, status=_St.COMPLETED)
        await stats_session.commit()

        stuck = await scraper_stats.find_stuck_pairs(stats_session)
        assert len(stuck) == 1, "only PENDING/RUNNING count as stuck"
        assert stuck[0]["city"] == "tehran"
        assert stuck[0]["status"] == "RUNNING"
        assert stuck[0]["running_over_minutes"] >= 89
        assert stuck_job.status == _St.RUNNING

        errors = await scraper_stats.collect_recent_errors(stats_session)
        assert errors == []  # no FAILED jobs yet

    _run(_inner())


def test_collect_city_health_respects_window(stats_session) -> None:
    """Health must cover the same window as the totals, or the panel lies."""
    from datetime import timedelta

    from app.models.base import utcnow
    from app.services import scraper_stats

    async def _inner() -> None:
        old = utcnow() - timedelta(days=3)
        _mk_job(stats_session, city="old-city", created_at=old, started_at=old,
                finished_at=old)
        _mk_job(stats_session, city="new-city")
        await stats_session.commit()

        recent = {h["city"] for h in await scraper_stats.collect_city_health(
            stats_session, hours=24)}
        assert recent == {"new-city"}, "a 3-day-old run must not show in a 24h window"

        wide = {h["city"] for h in await scraper_stats.collect_city_health(
            stats_session, hours=168)}
        assert wide == {"new-city", "old-city"}

    _run(_inner())


def test_collect_recent_errors_truncates(stats_session) -> None:
    from app.models.enums import ScrapeJobStatus as _St
    from app.services import scraper_stats

    async def _inner() -> None:
        _mk_job(stats_session, status=_St.FAILED, error="x" * 500)
        await stats_session.commit()
        errors = await scraper_stats.collect_recent_errors(stats_session)
        assert len(errors) == 1
        assert len(errors[0]["error"]) == 200, "errors must be truncated for the UI"

    _run(_inner())


def test_content_hash_price_bucketing() -> None:
    h1 = compute_content_hash("tehran", "x", 100.0, 2, 8_000_000_001)
    h2 = compute_content_hash("tehran", "x", 100.0, 2, 8_000_000_009)
    assert h1 == h2
    assert compute_content_hash("tehran", "x", 101.0, 2, 8_000_000_001) != h1
    h1 = compute_content_hash("tehran", "x", 100.0, 2, 8_000_000_001)
    h2 = compute_content_hash("tehran", "x", 100.0, 2, 8_000_000_009)
    assert h1 == h2
    assert compute_content_hash("tehran", "x", 101.0, 2, 8_000_000_001) != h1


def test_scheduler_creates_scheduled_jobs_per_city_category(session) -> None:
    """``session`` fixture bootstraps the shared schema used by the scheduler.

    Pinned to a single source so this stays a test of the city/category fan-out;
    the source dimension has its own test below.
    """
    from app.services.scraper_scheduler import ScrapeScheduler

    assert session is not None
    # Supported Delta cities, kept distinct from the overlap test below.
    sch = ScrapeScheduler(
        _sched_settings(scraper_cities="tehran,mashhad", scraper_sources="delta", scraper_scheduler_enabled=True),
        session_factory=_sqlite_sessionmaker(),
    )
    with _patched_scheduler() as launched:
        jobs = _run(sch.tick())
        assert len(jobs) == 2, "tehran + mashhad x apartment-sell"
        assert {(j.city, j.category) for j in jobs} == {
            ("tehran", "apartment-sell"),
            ("mashhad", "apartment-sell"),
        }
        for j in jobs:
            assert j.trigger.value == "SCHEDULED"
            assert j.params["max_pages"] == 2
            assert j.source == "delta"
            assert j.params["source_category"] == "apartment-sell"
        # Every created job was handed to the background runner.
        assert len(launched) == len(jobs)


def test_scheduler_covers_every_configured_source(session) -> None:
    """A tick must fan out over sources, not just city/category.

    The scheduler used to take no source at all, so every job fell back to the
    node default (Divar) and the other portals' feeds stayed permanently empty
    even though they were registered and reachable by API.
    """
    from app.services.scraper_scheduler import ScrapeScheduler

    assert session is not None
    sch = ScrapeScheduler(
        _sched_settings(
            scraper_cities="isfahan,shiraz", scraper_sources="delta", max_pages=1, scraper_scheduler_enabled=True
        ),
        session_factory=_sqlite_sessionmaker(),
    )
    with _patched_scheduler():
        jobs = _run(sch.tick())

    assert {j.source for j in jobs} == {"delta"}
    assert len(jobs) == 2, "2 cities x 1 category x 1 verified source"
    assert {j.city for j in jobs} == {"isfahan", "shiraz"}
    assert all(j.category == "apartment-sell" for j in jobs)
    assert all(j.params["source_category"] == "apartment-sell" for j in jobs)


def test_scheduler_defaults_to_every_registered_source(session) -> None:
    """An unset SCRAPER_SOURCES means "all of them", not "Divar only"."""
    from app.services.scraper import registry

    assert set(_sched_settings().source_list) == set(registry.source_keys())


def test_scheduler_ignores_an_unknown_source_name(session) -> None:
    """A typo must not take the whole scheduler down."""
    assert _sched_settings(scraper_sources="divar,bayreal").source_list == ("divar",)


def test_scheduler_skips_overlapping_job(session) -> None:
    """An existing PENDING job for the same pair blocks a duplicate."""
    from app.schemas.scraper import ScrapeJobCreate
    from app.services.scraper_scheduler import ScrapeScheduler

    payload = ScrapeJobCreate(source="delta", city="tehran", category="apartment-sell")
    _run(scraper_service.create_job(session, payload, settings=_verified_job_settings()))

    sch = ScrapeScheduler(
        _sched_settings(scraper_cities="tehran", scraper_sources="delta", scraper_scheduler_enabled=True),
        session_factory=_sqlite_sessionmaker(),
    )
    with _patched_scheduler():
        assert _run(sch.tick()) == []


def test_scheduler_does_not_treat_another_source_as_overlap(session) -> None:
    """The overlap guard is scoped per source.

    Without that scope a Delta job would mask the Divar job for the same
    city/category and only whichever portal was scheduled first would run.
    """
    from app.schemas.scraper import ScrapeJobCreate
    from app.services.scraper_scheduler import ScrapeScheduler

    payload = ScrapeJobCreate(source="sheypoor", city="tehran", category="houses-apartments-for-sale")
    _run(scraper_service.create_job(session, payload, settings=_verified_job_settings()))

    sch = ScrapeScheduler(
        _sched_settings(scraper_cities="tehran", scraper_sources="delta", scraper_scheduler_enabled=True, scraper_schedule_skip_overlapping=False),
        session_factory=_sqlite_sessionmaker(),
    )
    with _patched_scheduler():
        jobs = _run(sch.tick())

    assert [j.source for j in jobs] == ["delta"], "the Delta slot must not be masked by Sheypoor"


def test_scheduler_start_stop_is_idempotent() -> None:
    from app.services.scraper_scheduler import ScrapeScheduler

    sch = ScrapeScheduler(_sched_settings(scraper_schedule_interval_minutes=1))

    async def _inner() -> None:
        first = sch.start()
        second = sch.start()
        assert first is not None and first is second, "start() must not double-spawn"
        assert sch.running
        await sch.stop(timeout=5)
        assert not sch.running

    _run(_inner())


def test_scheduler_survives_failing_tick() -> None:
    """A broken tick must not kill the loop."""
    from app.services.scraper_scheduler import ScrapeScheduler

    sch = ScrapeScheduler(_sched_settings(scraper_schedule_interval_minutes=1))
    # Sub-second interval so the loop actually re-enters inside the test budget.
    sch.interval_seconds = lambda: 0.01  # type: ignore[method-assign]
    calls: list[int] = []

    async def _boom():
        calls.append(1)
        raise RuntimeError("boom")

    sch.tick = _boom

    async def _inner() -> None:
        sch.start()
        await asyncio.sleep(0.2)
        await sch.stop(timeout=5)
        # The loop caught the error and kept ticking.
        assert len(calls) >= 2, calls
        assert not sch.running

    _run(_inner())
    h1 = compute_content_hash("tehran", "x", 100.0, 2, 8_000_000_001)
    h2 = compute_content_hash("tehran", "x", 100.0, 2, 8_000_000_009)
    assert h1 == h2
    assert compute_content_hash("tehran", "x", 101.0, 2, 8_000_000_001) != h1


def _prop(external_id=None, content_hash=None) -> Property:
    return Property(
        title="t", property_type=PropertyType.APARTMENT, deal_type=DealType.SALE,
        status=PropertyStatus.ACTIVE, source=PropertySource.DIVAR_SCRAPER,
        external_id=external_id, content_hash=content_hash, raw_data={},
        has_elevator=False, has_parking=False, has_storage=False, has_balcony=False,
    )


def test_find_duplicate_by_external_and_hash(session: AsyncSession) -> None:
    async def _inner() -> None:
        session.add(_prop("QX1", "H1"))
        session.add(_prop("QX2", "H1"))
        await session.commit()
        dup = await find_duplicate(session, external_id="QX2", content_hash="OTHER")
        assert dup is not None and dup.external_id == "QX2"
        dup2 = await find_duplicate(session, external_id="ZZZ", content_hash="H1")
        assert dup2 is not None
        assert await find_duplicate(session, external_id="ZZZ", content_hash="ZZZ") is None
    _run(_inner())


def test_process_detail_persists_and_emits_event(session: AsyncSession) -> None:
    fired: list[dict] = []
    async def _listener(**kwargs):
        fired.append(kwargs)
    async def _inner():
        event_bus.clear(NEW_PROPERTY_INGESTED)
        event_bus.subscribe(NEW_PROPERTY_INGESTED, _listener)
        try:
            detail = DivarListingDetail(
                token="QX-EVT", title="apt", city="tehran", district="x", property_type=PropertyType.APARTMENT,
                total_price=9_000_000_000, area=110.0, rooms=2, floor=1,
                latitude=35.7, longitude=51.4, phone="09120000000",
            )
            outcome = await process_detail(session, detail, cipher=_cipher(), settings=TEST_SETTINGS)
            assert outcome.is_new
            return outcome
        finally:
            event_bus.clear(NEW_PROPERTY_INGESTED)
    outcome = _run(_inner())
    assert len(fired) == 1
    assert fired[0]["property_id"] == outcome.property_id


def test_process_detail_duplicate_updates(session: AsyncSession) -> None:
    async def _inner() -> None:
        cipher = _cipher()
        d1 = DivarListingDetail(token="QX-DUP", city="tehran", property_type=PropertyType.APARTMENT, area=100.0, phone="09120000000")
        first = await process_detail(session, d1, cipher=cipher, settings=TEST_SETTINGS)
        assert first.is_new
        d2 = DivarListingDetail(token="QX-DUP", city="tehran", property_type=PropertyType.APARTMENT, area=105.0, phone="09120000001")
        second = await process_detail(session, d2, cipher=cipher, settings=TEST_SETTINGS)
        assert second.is_duplicate
        assert second.property_id == first.property_id
    _run(_inner())


def test_pii_never_in_property_row(session: AsyncSession) -> None:
    async def _inner() -> None:
        cipher = _cipher()
        detail = DivarListingDetail(token="QX-PII", city="tehran", property_type=PropertyType.APARTMENT, phone="09120000000")
        outcome = await process_detail(session, detail, cipher=cipher, settings=TEST_SETTINGS)
        assert outcome.property_id is not None
        prop = await session.get(Property, outcome.property_id)
        assert prop is not None
        assert "09120000000" not in str(prop.model_dump())
        row = (await session.exec(PropertyOwnerPII.__table__.select().where(PropertyOwnerPII.property_id == outcome.property_id))).first()
        assert row is not None
        assert cipher.decrypt(row.owner_phone_enc) == "09120000000"
    _run(_inner())


def test_rescrape_without_phone_keeps_pii(session: AsyncSession) -> None:
    async def _inner() -> None:
        cipher = _cipher()
        d1 = DivarListingDetail(token="QX-KEEP", city="tehran", property_type=PropertyType.APARTMENT, phone="09120000000")
        first = await process_detail(session, d1, cipher=cipher, settings=TEST_SETTINGS)
        d2 = DivarListingDetail(token="QX-KEEP", city="tehran", property_type=PropertyType.APARTMENT, phone=None)
        second = await process_detail(session, d2, cipher=cipher, settings=TEST_SETTINGS)
        assert second.is_duplicate and second.property_id == first.property_id
        row = (await session.exec(PropertyOwnerPII.__table__.select().where(PropertyOwnerPII.property_id == first.property_id))).first()
        assert row is not None
        assert cipher.decrypt(row.owner_phone_enc) == "09120000000"
    _run(_inner())


def test_store_owner_pii_skips_without_phone(session: AsyncSession) -> None:
    import uuid as _uuid
    async def _inner() -> None:
        detail = DivarListingDetail(token="QX-NOPHONE", city="tehran", property_type=PropertyType.APARTMENT, phone=None)
        assert await store_owner_pii(session, _uuid.uuid4(), detail, _cipher()) is None
    _run(_inner())

def test_client_backoff_jittered() -> None:
    client = DivarClient(settings=TEST_SETTINGS)
    delays = {client.backoff_delay(2) for _ in range(20)}
    assert len(delays) > 1 and all(d >= 0 for d in delays)


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
    async def request(self, *a, **k):
        return self._responses.pop(0)


def test_client_retries_then_blocked() -> None:
    async def _inner() -> None:
        client = DivarClient(settings=TEST_SETTINGS)
        client._session = _FakeSession([_FakeResponse({}, 429)] * 10)
        try:
            await client.search("tehran", "apartment-sell", 1)
        except ScraperBlockedError:
            return
        raise AssertionError("expected ScraperBlockedError")
    _run(_inner())


def test_phone_extractor_disabled_by_default() -> None:
    async def _inner() -> None:
        assert await PhoneExtractor(settings=TEST_SETTINGS).extract("QX1") is None
    _run(_inner())


def test_phone_extractor_caches() -> None:
    async def _inner() -> None:
        enabled_settings = TEST_SETTINGS.model_copy(update={"phone_extraction_enabled": True})
        # A dedicated in-memory cache keeps the test isolated from the live
        # Redis node, otherwise a previous run's `phone:` key hides the client
        # call and the caching assertion becomes order-dependent.
        extractor = PhoneExtractor(
            settings=enabled_settings,
            cache=TokenCache(None),
        )
        class _Client:
            calls = 0
            async def get_contact_info(self, token):
                self.calls += 1
                return {"phone": "09120000000"}
        client = _Client()
        first = await extractor.extract("QX1", client=client)
        assert first == "09120000000"
        assert await extractor.extract("QX1", client=client) == first
        assert client.calls == 1
    _run(_inner())


def test_parse_phone_normalises() -> None:
    assert parse_phone({"phone": "0912-000-0000"}) == "09120000000"
    assert parse_phone({}) is None

def test_run_search_job_end_to_end(session) -> None:
    from dataclasses import replace as _dc_replace
    from app.services.scraper.parser import DivarListingDetail, DivarListingSummary
    from app.services.scraper.registry import get_source
    async def _inner():
        job = ScrapeJob(kind="SEARCH", source="delta", city="tehran", category="apartment-sell", params={"execution_scope": "test", "max_pages": 1})
        session.add(job)
        await session.commit()
        summaries = [DivarListingSummary(token="QX-J1", city="تهران"), DivarListingSummary(token="QX-J2", city="تهران")]
        class _Client:
            async def search(self, city, category, page, districts=None):
                return {}
            async def get_post(self, token):
                # district/area are read from label/value widget pairs (not
                # top-level keys); vary them so the two listings have distinct
                # content hashes and both count as NEW.
                suffix = "1" if token.endswith("1") else "2"
                return {
                    "title": token,
                    "city": "تهران",
                    "province": "تهران",
                    "__context": {"property_type": "apartment", "deal": "buy"},
                    "list_widgets": [
                        {"title": "متراژ", "value": "80" if suffix == "1" else "120"},
                        {"title": "محله", "value": f"zone-{suffix}"},
                    ],
                }
        # Divar's unverified city IDs prevent live job creation; this tests only
        # the isolated parser-to-ingestion pipeline with explicit fixture data.
        source = _dc_replace(
            get_source("delta"),
            parse_search=lambda payload: summaries,
            parse_detail=lambda payload, token, **kwargs: DivarListingDetail(
                token=token, title=token, city="تهران", province="تهران",
                district="zone", property_type=PropertyType.APARTMENT,
                area=80.0 if token.endswith("1") else 120.0,
                raw=payload,
            ),
        )
        job.source = "delta"
        job.params = {"execution_scope": "test", "max_pages": 1}
        settings = _verified_job_settings(scraper_sources="delta")
        return await run_search_job(session, job, client=_Client(), cipher=_cipher(), source=source, settings=settings, max_pages=1)
    job = _run(_inner())
    assert job.status.value == "COMPLETED"
    assert job.items_new == 2 and job.items_found == 2


def test_service_create_and_list(session) -> None:
    from app.schemas.scraper import ScrapeJobCreate
    from app.services import scraper_service
    async def _inner() -> None:
        payload = ScrapeJobCreate(source="delta", city="tehran", category="apartment-sell")
        job = await scraper_service.create_job(session, payload, settings=_verified_job_settings())
        assert job.status.value == "PENDING"
        jobs, total = await scraper_service.list_jobs(session)
        assert total >= 1 and any(j.id == job.id for j in jobs)
        assert await scraper_service.get_job(session, job.id) is not None
    _run(_inner())


def test_service_trigger_wait_runs_job(session) -> None:
    from app.schemas.scraper import ScrapeJobCreate
    import app.services.scraper_service as svc
    from app.services.scraper.parser import DivarListingDetail, DivarListingSummary
    class _FakeClient:
        def __init__(self, *a, **k):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def search(self, city, category, page, districts=None):
            return {"list_widgets": [{"data": {"token": "QX-TRIG", "title": "t"}}]}
        async def get_post(self, token):
            # Bare listings hash to the same fingerprint as leftovers from
            # earlier tests in the shared DB — vary district via a widget pair.
            return {
                "title": "t",
                "city": "تهران",
                "province": "تهران",
                "__context": {"property_type": "apartment", "deal": "buy"},
                "list_widgets": [{"title": "محله", "value": "trigger-zone"}],
            }
    # The client now comes from the source registry, so that is what has to be
    # swapped -- patching a module attribute would leave the real HTTP client in
    # place and put this test on the network.
    from dataclasses import replace as _dc_replace
    from app.services.scraper.registry import SOURCES
    real_source, real_cipher = SOURCES["delta"], svc.get_pii_cipher
    test_token = f"QX-TRIG-{id(session)}"
    fake_source = _dc_replace(
        real_source,
        client_factory=lambda settings=None: _FakeClient(),
        parse_search=lambda payload: [DivarListingSummary(token=test_token, city="تهران")],
        parse_detail=lambda payload, token, **kwargs: DivarListingDetail(
            token=token, title="t", city="تهران", province="تهران", property_type=PropertyType.APARTMENT, area=float(id(session) % 1000 + 80),
            raw=payload,
        ),
    )
    SOURCES["delta"] = fake_source
    svc.get_pii_cipher = lambda settings=None: _cipher()
    try:
        async def _inner():
            from app.services import scraper_service
            payload = ScrapeJobCreate(source="delta", city="tehran", category="apartment-sell")
            return await scraper_service.trigger_and_maybe_run(session, payload, settings=_verified_job_settings(), wait=True)
        job = _run(_inner())
        assert job.status.value == "COMPLETED"
        assert job.items_new == 1
        assert job.source == "delta"
    finally:
        SOURCES["delta"] = real_source
        svc.get_pii_cipher = real_cipher


def test_scraper_routes_registered_behind_license_guard() -> None:
    from app.api.v1.endpoints.scraper import router as scraper_router
    from app.main import app as fastapi_app
    # The endpoint router itself carries the license guard on every route.
    assert len(list(scraper_router.routes)) == 5
    for route in scraper_router.routes:
        dependant = getattr(route, "dependant", None)
        deps = getattr(dependant, "dependencies", []) if dependant else []
        dep_names = {d.call.__name__ for d in deps if d.call is not None}
        assert "verify_license_active" in dep_names
    # And the FastAPI app exposes the v1 endpoints (mounted with prefixes).
    # FastAPI >=0.142 wraps included routers in ``_IncludedRouter`` objects that
    # carry no ``path`` — walk them recursively to collect the final paths.
    from fastapi.routing import APIRoute, _IncludedRouter

    app_paths: set[str] = set()

    def _collect(routes, prefix: str = "") -> None:
        for r in routes:
            if isinstance(r, _IncludedRouter):
                sub = getattr(r.include_context, "prefix", "") or ""
                _collect(r.original_router.routes, prefix + sub)
            elif isinstance(r, APIRoute):
                app_paths.add(prefix + r.path)

    _collect(fastapi_app.routes)
    assert "/api/v1/scraper/trigger" in app_paths
    assert "/api/v1/scraper/jobs" in app_paths
    assert "/api/v1/scraper/jobs/{job_id}" in app_paths
    assert "/api/v1/scraper/set-focus-city" in app_paths


def test_scraper_trigger_forbidden_without_license() -> None:
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
    from app import main as main_module
    from app.api import deps as deps_module
    from app.core.identity import Principal, bootstrap_principal
    async def _deny(session=None, settings=None):
        raise HTTPException(status_code=403, detail={"error": "license_not_active"})
    # Identity is now enforced ahead of the licence check, so it has to be
    # satisfied here for the test to reach the licence guard it is about.
    main_module.app.dependency_overrides[deps_module.get_principal] = (
        lambda: bootstrap_principal()
    )
    main_module.app.dependency_overrides[deps_module.verify_license_active] = _deny
    try:
        client = TestClient(main_module.app, raise_server_exceptions=False)
        resp = client.post("/api/v1/scraper/trigger", json={"city": "tehran", "category": "apartment-sell"})
        assert resp.status_code == 403
    finally:
        main_module.app.dependency_overrides.pop(deps_module.verify_license_active, None)


def test_version_is_v2() -> None:
    from app import __version__
    assert __version__.startswith("2.0.0")


def test_property_source_enum_has_scraper() -> None:
    assert PropertySource.DIVAR_SCRAPER.value == "DIVAR_SCRAPER"
    assert PropertySource.DIVAR_KENAR.value == "DIVAR_KENAR"
