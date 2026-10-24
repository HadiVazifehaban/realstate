"""Tests that all models are registered and geometry columns are correct."""

from __future__ import annotations

from geoalchemy2 import Geometry
from sqlmodel import SQLModel

import app.models  # noqa: F401  (registers tables)
from app.models.base import polygon_column, point_column

EXPECTED_TABLES = {
    "agency_user",
    "client_demand",
    "node_license",
    "owner_access_log",
    "property",
    "property_media",
    "property_owner_pii",
    "scrape_job",
    "sync_outbox",
}


def test_all_tables_registered() -> None:
    assert EXPECTED_TABLES.issubset(set(SQLModel.metadata.tables))


def test_property_location_is_point_4326() -> None:
    col = SQLModel.metadata.tables["property"].c.location
    assert isinstance(col.type, Geometry)
    assert col.type.geometry_type == "POINT"
    assert col.type.srid == 4326


def test_demand_target_area_is_polygon_4326() -> None:
    col = SQLModel.metadata.tables["client_demand"].c.target_area
    assert isinstance(col.type, Geometry)
    assert col.type.geometry_type == "POLYGON"
    assert col.type.srid == 4326


def test_point_column_helper_spatial_index() -> None:
    col = point_column()
    # GeoAlchemy2 installs a spatial (GiST) index by default.
    assert col.type.geometry_type == "POINT"
    assert col.type.spatial_index is True


def test_polygon_column_helper() -> None:
    col = polygon_column()
    assert col.type.geometry_type == "POLYGON"
    assert col.type.srid == 4326


def test_sync_outbox_payload_column_exists() -> None:
    col = SQLModel.metadata.tables["sync_outbox"].c.payload
    assert col is not None


def test_property_visit_booking_table_registered() -> None:
    """The scheduler table is part of the metadata, with its unique slot."""
    from app.models import PropertyVisitBooking

    table = PropertyVisitBooking.__table__
    assert table.name == "property_visit_booking"
    assert {c.name for c in table.columns} >= {
        "property_id",
        "slot_date",
        "start_time",
        "end_time",
        "status",
        "kind",
    }
    unique = {c.name for uq in table.constraints for c in uq.columns}
    assert {"property_id", "slot_date", "start_time"} <= unique


def test_pii_unique_property_constraint() -> None:
    table = SQLModel.metadata.tables["property_owner_pii"]
    assert table.c.property_id.unique is True
