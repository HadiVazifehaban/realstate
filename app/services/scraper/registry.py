"""Registry of crawlable listing sources.

Every portal the node ingests from is described here once: which HTTP client
speaks to it, which parsers turn its payloads into the unified listing schema,
and which ``PropertySource`` its rows are stamped with. The ingestion pipeline
and the job service ask this module *which* source to run instead of importing
one portal's modules directly.

Why this module exists
----------------------
``run_search_job`` used to import Divar's ``parse_search_response`` /
``parse_post_detail`` and the job service used to construct ``DivarClient`` by
name. Both are correct for Divar and unusable for anyone else: the Sheypoor
client and parser were written, unit-tested -- and never executed, because
nothing could route a job to them. A new portal therefore meant editing the
pipeline rather than adding a file, and silently kept any second source dead.

Adding a source is now: write ``<name>_client.py`` / ``<name>_parser.py``
emitting the unified models, then register one :class:`ScraperSource` below.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from app.core.config import Settings
from app.models.enums import PropertySource
from app.services.scraper import cities
from app.services.scraper.divar_client import DivarClient, StealthClient
from app.services.scraper.delta_client import DeltaClient
from app.services.scraper.delta_parser import (
    parse_delta_detail,
    parse_delta_search,
)
from app.services.scraper.delta_taxonomy import (
    DELTA_CITIES,
    normalise_city as _validate_delta_city,
)
from app.services.scraper.parser import (
    DivarListingDetail,
    DivarListingSummary,
    parse_post_detail,
    parse_search_response,
)
from app.services.scraper.sheypoor_client import SheypoorClient
from app.services.scraper.sheypoor_parser import (
    parse_sheypoor_detail,
    parse_sheypoor_search,
)

# Source-agnostic names for the two models every parser emits. ``Divar*`` was the
# original spelling; these aliases are what new code should import.
UnifiedListingSummary = DivarListingSummary
UnifiedListingDetail = DivarListingDetail

ParseSearch = Callable[[dict], "list[UnifiedListingSummary]"]
ParseDetail = Callable[..., "UnifiedListingDetail"]


class UnknownSourceError(ValueError):
    """Raised when a job names a source the node does not know how to crawl."""

    def __init__(self, key: str) -> None:
        self.key = key
        known = ", ".join(sorted(SOURCES)) or "none"
        super().__init__(
            f"unknown scrape source {key!r}; registered sources: {known}"
        )


@dataclass(frozen=True)
class ScraperSource:
    """Everything the pipeline needs to crawl one portal."""

    key: str
    label: str
    property_source: PropertySource
    client_factory: Callable[[Settings], StealthClient]
    parse_search: ParseSearch
    parse_detail: ParseDetail
    #: Only Divar has the OTP-gated session flow, so ``fetch_phones`` is refused
    #: elsewhere instead of silently collecting nothing.
    supports_phone_extraction: bool = False
    #: Sources whose city/category slugs are portal-specific validate them
    #: against their own registry; others accept whatever the caller sent.
    validate_city: Callable[[str], None] | None = field(default=None)
    #: Same, for the optional neighbourhood narrowing. Divar is the only source
    #: with district ids today, so this is None elsewhere by design.
    validate_districts: Callable[[str, Sequence[str]], None] | None = field(default=None)
    #: False when the portal's search needs no category slug at all.
    supports_categories: bool = True
    #: Namespaces ``Property.external_id``, which carries a globally unique
    #: index. Two portals that both number their listings would otherwise
    #: overwrite each other, so every source added after Divar needs a prefix.
    #: Divar stays empty: its rows are already stored with the bare token.
    external_id_prefix: str = ""


def _validate_divar_city(city: str) -> None:
    """Raise on a slug Divar has no ``city_id`` for."""
    cities.get_city(city)


def _validate_divar_districts(city: str, districts: Sequence[str]) -> None:
    """Raise on a neighbourhood slug Divar has no district id for."""
    cities.resolve_district_ids(city, list(districts))


def _validate_sheypoor_city(city: str) -> None:
    """Sheypoor has no local id registry, so only the slug shape is checked."""
    slug = (city or "").strip().lower()
    if not slug or not slug.replace("-", "").isalnum():
        raise ValueError(
            f"{city!r} is not a Sheypoor city slug (expected e.g. 'tehran')"
        )


#: Registered sources, keyed by the value persisted in ``ScrapeJob.source``.
SOURCES: dict[str, ScraperSource] = {
    "divar": ScraperSource(
        key="divar",
        label="دیوار",
        property_source=PropertySource.DIVAR_SCRAPER,
        client_factory=DivarClient,
        parse_search=parse_search_response,
        parse_detail=parse_post_detail,
        supports_phone_extraction=True,
        validate_city=_validate_divar_city,
        validate_districts=_validate_divar_districts,
    ),
    "sheypoor": ScraperSource(
        key="sheypoor",
        label="شیپور",
        property_source=PropertySource.SHEYPOOR,
        client_factory=SheypoorClient,
        parse_search=parse_sheypoor_search,
        parse_detail=parse_sheypoor_detail,
        supports_phone_extraction=False,
        validate_city=_validate_sheypoor_city,
        external_id_prefix="sheypoor:",
    ),
    "delta": ScraperSource(
        key="delta",
        label="دلتا",
        property_source=PropertySource.DELTA,
        client_factory=DeltaClient,
        parse_search=parse_delta_search,
        parse_detail=parse_delta_detail,
        # Delta shows the broker's phone only behind an authenticated session the
        # node does not hold.
        supports_phone_extraction=False,
        validate_city=_validate_delta_city,
        # Delta's own detail URLs are already namespaced by their id space, which
        # is disjoint from Divar's, so a prefix is belt-and-braces.
        external_id_prefix="delta:",
    ),
}

#: Used when a job predates the ``source`` column, or a caller omits it.
DEFAULT_SOURCE_KEY = "divar"


def register_source(spec: ScraperSource, *, replace: bool = False) -> None:
    """Add a source to the registry.

    The extension point for a new portal. ``replace`` is required to displace
    an existing key, so an import order change can never silently swap sources.
    """
    existing = SOURCES.get(spec.key)
    if existing is not None and not replace:
        raise ValueError(
            f"scrape source {spec.key!r} is already registered as "
            f"{existing.client_factory.__name__}"
        )
    SOURCES[spec.key] = spec


def get_source(key: str | None) -> ScraperSource:
    """Resolve a source key, falling back to :data:`DEFAULT_SOURCE_KEY`."""
    if not key:
        return SOURCES[DEFAULT_SOURCE_KEY]
    try:
        return SOURCES[key.strip().lower()]
    except KeyError:
        raise UnknownSourceError(key) from None


def source_keys() -> tuple[str, ...]:
    return tuple(sorted(SOURCES))


def supports_phone_extraction(key: str | None) -> bool:
    """Whether ``fetch_phones`` can be honoured for this source."""
    return get_source(key).supports_phone_extraction


__all__ = [
    "ScraperSource",
    "UnknownSourceError",
    "UnifiedListingDetail",
    "UnifiedListingSummary",
    "SOURCES",
    "DEFAULT_SOURCE_KEY",
    "get_source",
    "register_source",
    "source_keys",
    "supports_phone_extraction",
]