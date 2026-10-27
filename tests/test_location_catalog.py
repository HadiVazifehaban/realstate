"""Location filters run offline over fixture inventory, never a live database."""

import sqlite3
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import column, select, table
from sqlalchemy.dialects import sqlite

from app.services.location_catalog import catalog, location_condition, resolve_city
from app.services.city_normalizer import is_known_city


def test_catalog_city_ids_are_composite_and_unique():
    provinces = catalog()["provinces"]
    ids = [c["id"] for p in provinces for c in p["cities"]]
    assert len(provinces) == 31
    assert len(ids) == len(set(ids))
    assert all(":" in cid for cid in ids)


def test_catalog_accepts_cities_outside_old_whitelist():
    assert is_known_city("چابهار")
    assert is_known_city("شهرکرد")
    assert not is_known_city("شهرک مریم")
    assert resolve_city("تبريز")["name"] == "تبریز"


def test_unknown_ids_fail_closed():
    model = SimpleNamespace(city=column("city"), province=column("province"))
    with pytest.raises(HTTPException) as error:
        location_condition(model, city_ids=["999:1"])
    assert error.value.status_code == 422


def test_multi_city_province_and_all_filter_stored_inventory():
    inventory = table("inventory", column("city"), column("province"), column("source"))
    model = SimpleNamespace(city=inventory.c.city, province=inventory.c.province)
    db = sqlite3.connect(":memory:")
    db.execute("create table inventory (city text, province text, source text)")
    db.executemany("insert into inventory values (?, ?, ?)", [
        ("تبريز", "آذربایجان شرقی", "internal"),
        ("مراغه", "آذربایجان شرقی", "divar"),
        ("تهران", "تهران", "sheypoor"),
        ("چابهار", "سیستان و بلوچستان", "delta"),
    ])

    def rows(**filters):
        condition = location_condition(model, **filters)
        query = select(inventory)
        if condition is not None:
            query = query.where(condition)
        compiled = query.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True})
        return db.execute(str(compiled)).fetchall()

    tabriz, tehran = resolve_city("تبریز"), resolve_city("تهران")
    assert {r[0] for r in rows(city_ids=[tabriz["id"], tehran["id"]])} == {"تبريز", "تهران"}
    assert len(rows(province_ids=[tabriz["province_id"]])) == 2
    assert len(rows()) == 4
    assert len(rows(city_ids=[resolve_city("چابهار")["id"]])) == 1
    assert rows(cities=["بدون موجودی"]) == []
    db.close()