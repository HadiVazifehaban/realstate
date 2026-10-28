"""Market-level aggregation over the node's own inventory.

The office already stores every listing it has seen; this module turns that
inventory into the *market view* a broker prices against — how many files each
neighbourhood holds, what the median asking price per square metre is there, how
much of it the AVM judged under-priced, and where the neighbourhood sits on the
map.

Everything is aggregated in PostGIS rather than in Python:

* ``percentile_cont(0.5)`` is the median the valuation engine already quotes, so
  the map and a single-property AVM verdict agree instead of drifting apart;
* one grouped query per request replaces thousands of rows shipped to the
  browser, which matters on an office node holding tens of thousands of files.

The one thing this module deliberately does *not* do is pretend to be an
appraisal. A neighbourhood median is a description of the asking prices on the
node — not its own inventory's verdict, and not a price for a specific unit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models import Property
from app.models.enums import DealType, PropertyStatus, ValuationStatus

#: Statuses that must never price the market: withdrawn, archived or already
#: transacted inventory would drag a neighbourhood median towards whatever the
#: desk happened to close last month.
EXCLUDED_STATUSES: frozenset[PropertyStatus] = frozenset(
    {
        PropertyStatus.WITHDRAWN,
        PropertyStatus.ARCHIVED,
        PropertyStatus.DRAFT,
    }
)


@dataclass(frozen=True)
class NeighbourhoodStat:
    """One neighbourhood's slice of the market, ready to be drawn."""

    neighborhood: str
    city: str
    #: Listings that actually carry the price this row is describing. A row with
    #: `files == 0` is dropped, so a median always has a numerator.
    files: int
    #: Every file in the neighbourhood, priced or not -- the coverage figure the
    #: UI needs to say "۱۸ از ۴۰ فایل قیمت دارد" instead of implying completeness.
    all_files: int
    median_price_per_meter: int | None = None
    median_total_price: int | None = None
    median_deposit: int | None = None
    median_monthly_rent: int | None = None
    median_area: float | None = None
    #: Share of *all* files the engine judged below market, 0..1.
    bargain_share: float = 0.0
    median_deviation_pct: float | None = None
    #: Mean of the listing coordinates. A mean, not a centroid: a neighbourhood
    #: whose files cluster on one street should place its bubble there.
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True)
class MarketOverview:
    """The city-level totals the page header shows alongside the map."""

    deal_types: list[DealType]
    city: str | None
    neighbourhoods: list[NeighbourhoodStat] = field(default_factory=list)
    #: Files matching the base filter, priced or not, and the priced subset.
    total_files: int = 0
    priced_files: int = 0
    median_price_per_meter: int | None = None
    bubbles: int = 0


def _priced_condition(deal_types: list[DealType]):
    """Which listing counts as 'priced' for this deal type.

    A sale without a per-metre price cannot describe price per metre, and a rent
    is quoted as deposit + monthly rent, so the two families need different
    columns. Requiring the wrong one would silently drop every rent.
    """
    only_rent = all(deal_type in (DealType.RENT, DealType.FULL_MORTGAGE) for deal_type in deal_types)
    if only_rent:
        return Property.deposit_amount.is_not(None) | Property.monthly_rent.is_not(None)
    return Property.price_per_meter.is_not(None)


def _rows_to_stats(rows: list) -> list[NeighbourhoodStat]:
    """Shape raw grouped rows into stats.

    Split out from the query so the arithmetic — the bargain share denominator
    above all — is asserted without a database.
    """
    stats: list[NeighbourhoodStat] = []
    for row in rows:
        (
            city,
            neighborhood,
            files,
            all_files,
            median_ppm,
            median_total,
            median_deposit,
            median_rent,
            median_area,
            bargains,
            median_deviation,
            latitude,
            longitude,
        ) = row

        files = int(files or 0)
        all_files = int(all_files or 0)
        if files <= 0 or not neighborhood:
            continue

        # Share of every file, not of the priced ones: a neighbourhood with one
        # priced file and nine unpriced bargains is not a 100% bargain market,
        # and quoting it as one would send a broker to inspect nothing.
        share = (int(bargains or 0) / all_files) if all_files else 0.0

        stats.append(
            NeighbourhoodStat(
                neighborhood=neighborhood,
                city=city or "",
                files=files,
                all_files=all_files,
                median_price_per_meter=_int_or_none(median_ppm),
                median_total_price=_int_or_none(median_total),
                median_deposit=_int_or_none(median_deposit),
                median_monthly_rent=_int_or_none(median_rent),
                median_area=float(median_area) if median_area is not None else None,
                bargain_share=round(share, 4),
                median_deviation_pct=(
                    float(median_deviation) if median_deviation is not None else None
                ),
                latitude=float(latitude) if latitude is not None else None,
                longitude=float(longitude) if longitude is not None else None,
            )
        )
    return stats


def _int_or_none(value: object) -> int | None:
    """``percentile_cont`` answers with a float even for a BIGINT column."""
    if value is None:
        return None
    return int(round(float(value)))


async def neighbourhood_market(
    session: AsyncSession,
    *,
    city: str | None = None,
    city_ids: list[str] | None = None,
    province_ids: list[str] | None = None,
    cities: list[str] | None = None,
    deal_types: list[DealType] | None = None,
    min_files: int = 1,
    limit: int = 200,
    visibility=None,
) -> MarketOverview:
    """Per-neighbourhood medians for one city (or the whole node)."""
    types = deal_types or [DealType.SALE]
    priced = _priced_condition(types)

    # `priced` is deliberately *not* a WHERE condition: the row still needs the
    # unpriced files in the neighbourhood, both for the coverage figure
    # (`all_files`) and because a bargain the engine flagged may well be one of
    # them. It narrows the priced count in the select and the HAVING only.
    conditions = [
        Property.deal_type.in_(types),
        Property.status.not_in(list(EXCLUDED_STATUSES)),
        Property.neighborhood != "",
    ]
    if visibility is not None:
        conditions.append(visibility)
    from app.services.location_catalog import location_condition

    location = location_condition(Property, city_ids=city_ids, province_ids=province_ids,
                                  cities=cities or ([city] if city else None))
    if location is not None:
        conditions.append(location)

    bargains = func.count().filter(Property.valuation_status == ValuationStatus.BARGAIN)

    rows = (
        await session.exec(
            select(
                Property.city,
                Property.neighborhood,
                # Priced count first, then every file: `_rows_to_stats` reads
                # them in this order.
                func.count().filter(priced),
                func.count(),
                func.percentile_cont(0.5).within_group(Property.price_per_meter),
                func.percentile_cont(0.5).within_group(Property.total_price),
                func.percentile_cont(0.5).within_group(Property.deposit_amount),
                func.percentile_cont(0.5).within_group(Property.monthly_rent),
                func.percentile_cont(0.5).within_group(Property.area),
                bargains,
                func.percentile_cont(0.5).within_group(Property.valuation_deviation_pct),
                func.avg(Property.latitude),
                func.avg(Property.longitude),
            )
            .where(*conditions)
            .group_by(Property.city, Property.neighborhood)
            .having(func.count().filter(priced) >= min_files)
            .order_by(func.count().filter(priced).desc())
            .limit(limit)
        )
    ).all()

    stats = _rows_to_stats([tuple(row) for row in rows])

    # Totals are counted separately from the bubble rows: `limit` may cut the
    # list short, and a header that silently reports only the cards it drew
    # would understate the city.
    total_files, priced_files, city_median = await _totals(
        session, city=city, deal_types=types, location=location, visibility=visibility
    )

    return MarketOverview(
        deal_types=types,
        city=city,
        neighbourhoods=stats,
        total_files=total_files,
        priced_files=priced_files,
        median_price_per_meter=_int_or_none(city_median),
        bubbles=len(stats),
    )


async def _totals(
    session: AsyncSession, *, city: str | None, deal_types: list[DealType], location=None,
    visibility=None,
) -> tuple[int, int, float | None]:
    priced = _priced_condition(deal_types)
    conditions = [
        Property.deal_type.in_(deal_types),
        Property.status.not_in(list(EXCLUDED_STATUSES)),
    ]
    if location is not None:
        conditions.append(location)
    elif city:
        conditions.append(Property.city == city)
    if visibility is not None:
        conditions.append(visibility)

    row = (
        await session.exec(
            select(
                func.count(),
                func.count().filter(priced),
                func.percentile_cont(0.5).within_group(Property.price_per_meter),
            ).where(*conditions)
        )
    ).one()

    return int(row[0] or 0), int(row[1] or 0), row[2]
