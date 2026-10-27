"""Fail-closed category mappings for source-specific scraper routes.

The registry is derived from the source taxonomies already pinned in this
package. Unknown categories are deliberately not guessed or forwarded.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.scraper.delta_taxonomy import DELTA_PROPERTY_TYPES
from app.services.scraper.sheypoor_taxonomy import SHEYPOOR_CATEGORIES


class UnsupportedCategoryError(ValueError):
    """A requested generic category has no verified mapping for its source."""

    status = "UNSUPPORTED"


class JobValidationError(ValueError):
    """Structured fail-closed error raised before a scrape job is persisted."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class CategoryResolution:
    source: str
    requested: str
    categories: tuple[str, ...]
    status: str = "SUPPORTED"


GENERIC_CATEGORIES = frozenset(
    {
        "apartment-sell",
        "apartment-rent",
        "house-villa-sell",
        "house-villa-rent",
    }
)

# The apartment routes are the existing, source-confirmed Delta type/deal
# combination. Delta has a `villa` property type, but no taxonomy evidence that
# generic house/villa categories have the same listing scope; keep them rejected.
_DELTA_MAP = {
    "apartment-sell": ("apartment-sell",),
    "apartment-rent": ("apartment-rent",),
}

# Sheypoor's verified taxonomy has combined houses/apartments for sale and rent.
# Both generic property scopes map to that one source category; tuple values keep
# expansion explicit and stable without duplicate route requests.
_SHEYPOOR_APARTMENT_SALE = "houses-apartments-for-sale"
_SHEYPOOR_APARTMENT_RENT = "house-apartment-for-rent"
_SHEYPOOR_VERIFIED = {row.slug for row in SHEYPOOR_CATEGORIES if row.category_id is not None}
_SHEYPOOR_MAP = {
    "apartment-sell": (_SHEYPOOR_APARTMENT_SALE,),
    "house-villa-sell": (_SHEYPOOR_APARTMENT_SALE,),
    "apartment-rent": (_SHEYPOOR_APARTMENT_RENT,),
    "house-villa-rent": (_SHEYPOOR_APARTMENT_RENT,),
}


def resolve_categories(source: str, category: str) -> CategoryResolution:
    """Return verified source category slug(s), preserving unsupported status."""
    source_key = (source or "").strip().lower()
    requested = (category or "").strip().lower()
    if requested not in GENERIC_CATEGORIES:
        raise UnsupportedCategoryError("category is not in the supported generic taxonomy")

    if source_key == "delta":
        result = _DELTA_MAP.get(requested)
        if result is None:
            raise UnsupportedCategoryError(f"{requested} is unsupported by Delta")
        # Assert the route's property portion remains inside Delta's own registry.
        property_type = result[0].rsplit("-", 1)[0]
        if property_type not in DELTA_PROPERTY_TYPES:
            raise UnsupportedCategoryError(f"{requested} has no verified Delta property type")
    elif source_key == "sheypoor":
        result = _SHEYPOOR_MAP.get(requested)
        if result is None or any(slug not in _SHEYPOOR_VERIFIED for slug in result):
            raise UnsupportedCategoryError(f"{requested} has no verified Sheypoor mapping")
    else:
        raise UnsupportedCategoryError("source has no verified category mapping")

    # Stable de-duplication protects future explicit expansions from duplicate
    # source requests while preserving taxonomy order.
    unique = tuple(dict.fromkeys(result))
    if not unique:
        raise UnsupportedCategoryError(f"{requested} has no source category")
    return CategoryResolution(source_key, requested, unique)


def validate_job_target(source: str, city: str, category: str, settings) -> CategoryResolution:
    """Validate enablement and source-specific target before creating a job.

    `city` is expected to be the source's own city slug. Curated city crosswalk
    validation is delegated to the source registry and is separately required
    for sources whose registry is only syntactic.
    """
    from app.services.scraper.registry import get_source

    key = (source or "").strip().lower()
    if not settings.scraper_enabled:
        raise JobValidationError("DISABLED_SOURCE", "scraper is disabled")
    if key not in settings.source_list:
        raise JobValidationError("DISABLED_SOURCE", "source is not enabled")
    try:
        source_spec = get_source(key)
    except Exception as exc:
        raise JobValidationError("DISABLED_SOURCE", "source is not registered") from exc
    if key not in {"divar", "sheypoor", "delta"}:
        raise JobValidationError("DISABLED_SOURCE", "source has no verified job mapping")

    city_slug = (city or "").strip().lower()
    if not city_slug:
        raise JobValidationError("UNMAPPED_CITY", "city is required")
    if key == "delta":
        from app.services.scraper.delta_taxonomy import normalise_city

        try:
            normalise_city(city_slug)
        except ValueError as exc:
            raise JobValidationError("UNMAPPED_CITY", "city has no Delta taxonomy mapping") from exc
    elif key == "sheypoor":
        from app.services.scraper.demand_locations import demand_location

        city_row = demand_location(city_slug)
        if city_row is None and city_slug.isascii():
            from app.services.scraper.demand_locations import canonical_demand_city

            city_row = canonical_demand_city(city_slug)
        if city_row is None:
            raise JobValidationError("UNMAPPED_CITY", "city has no verified Sheypoor crosswalk")
        if not city_row.get("slug"):
            raise JobValidationError("UNMAPPED_CITY", "city has no Sheypoor source slug")
        if city_row["slug"] != city_slug and city_row["name"].lower() != city_slug:
            raise JobValidationError("UNMAPPED_CITY", "use the source-specific Sheypoor city slug")
    try:
        if source_spec.validate_city is not None:
            source_spec.validate_city(city_slug)
    except (TypeError, ValueError) as exc:
        raise JobValidationError("UNVERIFIED_CITY", "city is not valid for source") from exc

    # A syntactically valid slug is not proof of a source crosswalk. Divar's
    # own API path is deliberately blocked unless its registry is verified.
    if key == "divar":
        from app.services.scraper.cities import get_city

        try:
            divar_city = get_city(city_slug)
        except ValueError as exc:
            raise JobValidationError("UNMAPPED_CITY", "city has no Divar mapping") from exc
        if not divar_city.is_verified:
            raise JobValidationError("UNVERIFIED_CITY", "Divar city mapping is unverified")

    try:
        return resolve_categories(key, category)
    except UnsupportedCategoryError as exc:
        # Legacy/internal taxonomy entries are permitted only when the source
        # owns a category validator; generic cross-source slugs stay fail-closed.
        if key == "divar":
            from app.services.scraper.parser import map_category

            if map_category(category) is not None:
                return CategoryResolution(key, category, (category,))
        raise JobValidationError("UNSUPPORTED_CATEGORY", str(exc)) from exc


__all__ = [
    "CategoryResolution",
    "JobValidationError",
    "UnsupportedCategoryError",
    "resolve_categories",
    "validate_job_target",
]