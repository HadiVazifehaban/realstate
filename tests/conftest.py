"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.crypto import PiiCipher  # noqa: E402


@pytest.fixture()
def cipher() -> PiiCipher:
    return PiiCipher(PiiCipher.generate_key())


@pytest.fixture()
def temp_key_file(tmp_path: Path) -> Path:
    return tmp_path / "keys" / "agency_pii.key"


def sqlite_safe_tables(*table_names: str):
    """Copy the named tables into a SQLite-safe schema.

    GeoAlchemy2 ``Geometry`` columns compile to PostGIS calls (and are read back
    through ``RecoverGeometryColumn``), which SQLite cannot serve. Tests that only
    exercise non-spatial logic copy the tables and downgrade the geometry columns
    to TEXT so ``create_all`` and ``refresh`` work without a live PostGIS.
    """
    from sqlalchemy import MetaData, String
    from sqlalchemy.dialects.postgresql import ARRAY as PgArray
    from sqlalchemy.dialects.postgresql import ENUM as PgEnum
    from geoalchemy2 import Geometry
    from sqlmodel import SQLModel

    own = MetaData()
    # Copy transitively: a table's foreign keys must resolve inside the new
    # MetaData, so pull in every referenced table too.
    pending = list(table_names)
    seen: set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        table = SQLModel.metadata.tables[name]
        table.to_metadata(own)
        pending.extend(
            fk.column.table.name for fk in table.foreign_keys
        )
    for table in own.tables.values():
        for column in table.columns:
            if isinstance(column.type, Geometry):
                column.type = String()
            elif isinstance(column.type, PgEnum):
                column.type = String(64)
            elif isinstance(column.type, PgArray):
                from sqlalchemy import JSON

                column.type = JSON()
    return list(own.tables.values())


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
    # Little-endian EWKB point with the SRID flag set.
    return _struct.pack("<BIIdd", 1, 0x20000000 | 1, srid, x, y).hex()


def register_sqlite_spatial_udfs(engine) -> None:
    """Emulate the PostGIS functions GeoAlchemy2 compiles to.

    The ORM keeps its real ``Geometry`` column types, so INSERTs call
    ``GeomFromEWKT`` and reads go through ``RecoverGeometryColumn``/``AsEWKB``.
    SQLite ships none of them, so plain-Python UDFs stand in.
    """
    from sqlalchemy import event

    if getattr(engine.sync_engine, "_avg_spatial_udfs", False):
        return

    @event.listens_for(engine.sync_engine, "connect")
    def _install(dbapi_conn, _record) -> None:
        dbapi_conn.create_function("GeomFromEWKT", -1, _sqlite_geom_from_ewkt)
        dbapi_conn.create_function("AsEWKB", 1, _sqlite_as_ewkb)
        dbapi_conn.create_function(
            "RecoverGeometryColumn", 5, lambda *args: args[0]
        )

    engine.sync_engine._avg_spatial_udfs = True


async def create_sqlite_schema(engine, *table_names: str) -> None:
    """Prepare a SQLite engine for the given tables and return nothing.

    Registers the spatial UDFs (the ORM still binds PostGIS calls) and creates the
    schema with geometry columns downgraded to TEXT.
    """
    from sqlmodel import SQLModel  # noqa: F401  (ensures tables are registered)

    register_sqlite_spatial_udfs(engine)
    tables = sqlite_safe_tables(*table_names)
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: SQLModel.metadata.create_all(c, tables=tables))
