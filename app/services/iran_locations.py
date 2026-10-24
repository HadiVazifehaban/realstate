"""Province -> county tree from the self-hosted Iran Locations API.

The listing filter's city cascade used to depend on an external map platform, which
answers ``480 API Key not found`` for a node whose key is a placeholder and
leaves the dropdown empty. This module talks to the vendored
``services/iran-locations-api`` container instead: it serves the same
administrative tree from a local JSON dataset, needs no platform key, and is
one hop away on the internal Docker network.

The response is normalized into the exact shape the GIS endpoints already
return, so callers (and the browser) cannot tell which provider answered:

    {"provinces": [{"name": "خراسان رضوی", "cities": ["مشهد", ...]}],
     "cities": ["مشهد", ...]}

Why the names are transliterated: the dataset spells several provinces and
cities with Arabic ``ي``/``ك`` (``"آذربايجان شرقي"``, ``"شهركرد"``) while the
crawler writes Persian ``ی``/``ک``. The radar filters on an exact match against
``Property.city``, so a raw ``"تبريز"`` would match nothing -- every name is
folded to Persian orthography before it leaves this module.
"""

from __future__ import annotations

import logging
from time import monotonic
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

AREAS_CACHE_TTL_SECONDS = 86_400
REQUEST_TIMEOUT_SECONDS = 15.0

# Arabic yeh/kaf -> Persian, plus the Arabic-Indic variants the dataset mixes in
# for digits and the separators it uses between city names.
#
# Every key must be exactly one character: `str.maketrans` builds a per-codepoint
# table, and a multi-character key (a yeh glued to a tatweel, say) raises
# `ValueError` at import -- which takes the whole API down, not just this module.
_TRANSLITERATION = str.maketrans(
    {
        "ي": "ی",  # ي -> ی
        "ك": "ک",  # ك -> ک
        "ﻙ": "ک",
        "ﻚ": "ک",
        "ى": "ی",  # ى -> ی
        "ۀ": "ه",  # ة -> ه (compile as-te marbuta to a bare heh for matching)
        "ة": "ه",
        "ـ": None,  # tatweel: a decorative stretch, dropped before matching
    }
)

_tree_cache: tuple[float, dict[str, Any]] | None = None


def _fold(name: str) -> str:
    """Fold Arabic orthography to the Persian spelling the CRM stores."""
    return name.strip().translate(_TRANSLITERATION).strip()


def _base_url() -> str:
    return get_settings().iran_locations_url.rstrip("/")


def _dedupe(names: list[str]) -> list[str]:
    """Keep first-seen order, dropping the duplicates the fan-out produces."""
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


async def _get(client: httpx.AsyncClient, path: str) -> Any:
    response = await client.get(f"{_base_url()}{path}")
    response.raise_for_status()
    return response.json()


async def fetch_areas_tree() -> dict[str, Any]:
    """The whole province -> county tree, cached for a day.

    One request for the province list plus one per province for its counties
    (the ``/states`` route deliberately omits the nested ``cities``), so the
    first call fans out 32 requests and every later one is a cache hit.
    """
    global _tree_cache

    now = monotonic()
    if _tree_cache is not None and now - _tree_cache[0] < AREAS_CACHE_TTL_SECONDS:
        return _tree_cache[1]

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            states = await _get(client, "/api/v1/fa/states")
            if not isinstance(states, list):
                raise ValueError("unexpected /states payload")

            provinces: list[dict[str, Any]] = []
            all_cities: list[str] = []
            for state in states:
                if not isinstance(state, dict):
                    continue
                name = _fold(str(state.get("name") or ""))
                state_id = state.get("id")
                cities: list[str] = []
                if state_id is not None:
                    rows = await _get(client, f"/api/v1/fa/cities?state_id={state_id}")
                    if isinstance(rows, list):
                        cities = _dedupe(
                            [
                                folded
                                for folded in (_fold(str(c.get("name") or "")) for c in rows if isinstance(c, dict))
                                if folded
                            ]
                        )
                if not name:
                    continue
                provinces.append({"name": name, "cities": cities})
                all_cities.extend(cities)
    except (httpx.HTTPError, ValueError) as exc:
        # An unreachable container must degrade to the caller's fallback, not
        # raise: the endpoint answering an empty tree is handled downstream.
        logger.warning("iran-locations tree unavailable: %s", exc)
        return {}

    tree = {"provinces": provinces, "cities": _dedupe(all_cities)}
    _tree_cache = (now, tree)
    return tree
