"""Identity and SQL filtering over the vendored (not scraper) location catalog.

City numbers restart in each province. Public city IDs are therefore the
composite ``province_id:local_city_id``, never a portal's numeric identifier.
No network request, crawler, or database write is made by this module.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import and_, false, func, or_

from app.services.iran_locations import _fold

CATALOG_PATH = (
    Path(__file__).resolve().parents[2]
    / "services/iran-locations-api/public/iran_cities_with_coordinates.json"
)


def normalized_name(value: str) -> str:
    return _fold(value).replace("\u200c", "").replace(" ", "")


@lru_cache(maxsize=1)
def catalog() -> dict:
    provinces = []
    for province in json.loads(CATALOG_PATH.read_text(encoding="utf-8")):
        province_id = str(province["id"])
        cities = [
            {
                "id": f"{province_id}:{city['id']}",
                "local_id": city["id"],
                "province_id": province_id,
                "province": _fold(province["name"]),
                "name": _fold(city["name"]),
            }
            for city in province["cities"]
        ]
        provinces.append({"id": province_id, "name": _fold(province["name"]),
                          "cities": cities})
    return {"provinces": provinces}


def resolve_city(name: str, province: str = "") -> dict | None:
    candidates = [
        city for p in catalog()["provinces"] for city in p["cities"]
        if normalized_name(city["name"]) == normalized_name(name)
        and (not province or normalized_name(p["name"]) == normalized_name(province))
    ]
    return candidates[0] if len(candidates) == 1 else None


def _sql_name(column):
    for original, replacement in (("ي", "ی"), ("ى", "ی"), ("ك", "ک"),
                                  ("\u200c", ""), (" ", "")):
        column = func.replace(column, original, replacement)
    return column


def location_condition(model, *, city_ids=None, province_ids=None, cities=None):
    """Union selected cities/provinces; legacy city names additionally narrow it.

    Unknown IDs fail closed (422). No selection means unrestricted inventory.
    Ambiguous legacy city names without a province cannot safely be assigned to
    an ID and are intentionally excluded from ID-scoped queries.
    """
    provinces = {p["id"]: p for p in catalog()["provinces"]}
    all_cities = {c["id"]: c for p in provinces.values() for c in p["cities"]}
    requested_cities = set(city_ids or [])
    requested_provinces = set(province_ids or [])
    unknown = (requested_cities - all_cities.keys()) | (requested_provinces - provinces.keys())
    if unknown:
        raise HTTPException(422, detail={"error": "invalid_location_ids", "ids": sorted(unknown)})
    selected = requested_cities | {
        c["id"] for pid in requested_provinces for c in provinces[pid]["cities"]
    }
    clauses = []
    if selected:
        by_name: dict[str, list[dict]] = {}
        for city in all_cities.values():
            by_name.setdefault(normalized_name(city["name"]), []).append(city)
        selections = []
        for cid in selected:
            city = all_cities[cid]
            name_match = _sql_name(model.city) == normalized_name(city["name"])
            if len(by_name[normalized_name(city["name"])]) > 1:
                name_match = and_(name_match, _sql_name(model.province) == normalized_name(city["province"]))
            selections.append(name_match)
        clauses.append(or_(*selections) if selections else false())
    if cities:
        clauses.append(_sql_name(model.city).in_([normalized_name(c) for c in cities]))
    return and_(*clauses) if clauses else None