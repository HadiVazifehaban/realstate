/**
 * Metric, colour and sizing rules for the market map.
 *
 * Kept out of the components for one reason: the map, the legend and the list
 * must agree on what "expensive" means. When each of them derived its own
 * scale, a neighbourhood could read red in the list and blue in its bubble.
 */

import { formatPricePerMeter, formatToman, toPersianDigits } from '@/lib/utils';

import type { DealType, NeighbourhoodStat, PropertySummary } from '../types';

/**
 * Deal families, as a broker thinks of them.
 *
 * `FULL_MORTGAGE` is a rent with no monthly payment, so it belongs with `RENT`
 * on every screen; splitting them would leave two half-empty maps. The API
 * receives the concrete `DealType` members this expands to.
 */
export const DEAL_GROUPS = ['SALE', 'RENT'] as const;
export type DealGroup = (typeof DEAL_GROUPS)[number];

export const DEAL_GROUP_LABELS: Record<DealGroup, string> = {
  SALE: 'فروش',
  RENT: 'رهن و اجاره'
};

export function dealTypesFor(group: DealGroup): DealType[] {
  return group === 'SALE' ? ['SALE'] : ['RENT', 'FULL_MORTGAGE'];
}

export type MarketMetricId =
  | 'price_per_meter'
  | 'total_price'
  | 'deposit'
  | 'monthly_rent'
  | 'files'
  | 'bargain_share';

export interface MarketMetric {
  id: MarketMetricId;
  label: string;
  /** Short unit note shown on the legend, e.g. «تومان/متر». */
  unit: string;
  /** Which deal family the metric is meaningful for, or 'both'. */
  group: DealGroup | 'both';
  /** The number drawn, or null when the data cannot answer it. */
  pick: (stat: NeighbourhoodStat) => number | null;
  format: (value: number) => string;
}

const countFormatter = (value: number) =>
  `${toPersianDigits(Math.round(value).toLocaleString('en-US'))}`;

export const MARKET_METRICS: MarketMetric[] = [
  {
    id: 'price_per_meter',
    label: 'قیمت هر متر',
    unit: 'تومان/متر',
    group: 'SALE',
    pick: (stat) => stat.median_price_per_meter,
    format: (value) => formatPricePerMeter(value)
  },
  {
    id: 'total_price',
    label: 'میانهٔ قیمت کل',
    unit: 'تومان',
    group: 'SALE',
    pick: (stat) => stat.median_total_price,
    format: (value) => formatToman(value)
  },
  {
    id: 'deposit',
    label: 'میانهٔ ودیعه',
    unit: 'تومان',
    group: 'RENT',
    pick: (stat) => stat.median_deposit,
    format: (value) => formatToman(value)
  },
  {
    id: 'monthly_rent',
    label: 'میانهٔ اجارهٔ ماهانه',
    unit: 'تومان',
    group: 'RENT',
    pick: (stat) => stat.median_monthly_rent,
    format: (value) => formatToman(value)
  },
  {
    id: 'files',
    label: 'تعداد فایل',
    unit: 'فایل',
    group: 'both',
    pick: (stat) => stat.files,
    format: (value) => `${countFormatter(value)} فایل`
  },
  {
    id: 'bargain_share',
    label: 'سهم زیر بازار',
    unit: '٪',
    group: 'both',
    // Share of every file, so a neighbourhood holding one priced bargain among
    // nine unpriced files cannot top the list.
    pick: (stat) => stat.bargain_share * 100,
    format: (value) => `${toPersianDigits(value.toFixed(1))}٪`
  }
];

/** The metrics that make sense for the chosen deal family, in display order. */
export function metricsFor(group: DealGroup): MarketMetric[] {
  return MARKET_METRICS.filter(
    (metric) => metric.group === 'both' || metric.group === group
  );
}

export function metricById(id: MarketMetricId): MarketMetric {
  return MARKET_METRICS.find((metric) => metric.id === id) ?? MARKET_METRICS[0]!;
}

/**
 * Colour ramp, cheap to expensive.
 *
 * Blue through green and yellow to red is the reading every heat map in the
 * region uses, so a broker needs no legend to know which end is which; the
 * legend is there to attach numbers to it, not to teach the direction.
 */
const RAMP: Array<[number, [number, number, number]]> = [
  [0.0, [59, 130, 246]],
  [0.25, [34, 197, 94]],
  [0.5, [234, 179, 8]],
  [0.75, [249, 115, 22]],
  [1.0, [239, 68, 68]]
];

/** Colour at a 0..1 position on the ramp. */
export function colorAt(position: number): string {
  const clamped = Math.min(1, Math.max(0, position));
  for (let index = 1; index < RAMP.length; index += 1) {
    const [stop, rgb] = RAMP[index]!;
    const [previousStop, previousRgb] = RAMP[index - 1]!;
    if (clamped <= stop) {
      const span = stop - previousStop || 1;
      const t = (clamped - previousStop) / span;
      const mix = rgb.map((channel, channelIndex) =>
        Math.round(previousRgb[channelIndex]! + (channel - previousRgb[channelIndex]!) * t)
      );
      return `rgb(${mix[0]} ${mix[1]} ${mix[2]})`;
    }
  }
  return 'rgb(239 68 68)';
}

export interface MarketScale {
  min: number;
  max: number;
  median: number | null;
}

/**
 * Scale bounds for the drawn values.
 *
 * Clamped at the 2nd and 98th percentile rather than the extremes: one portal
 * listing at ten times the neighbourhood price would otherwise flatten every
 * other bubble to the same shade of blue, which is the failure mode this whole
 * screen exists to avoid.
 */
export function scaleOf(values: number[]): MarketScale {
  const sorted = values.filter((value) => Number.isFinite(value)).sort((a, b) => a - b);
  if (sorted.length === 0) return { min: 0, max: 0, median: null };

  const at = (quantile: number) =>
    sorted[Math.min(sorted.length - 1, Math.max(0, Math.round(quantile * (sorted.length - 1))))]!;

  const min = at(0.02);
  const max = at(0.98);
  return {
    min,
    // A single-valued scale would divide by zero; keep a hair of width so the
    // one bubble that exists renders mid-ramp instead of black.
    max: max > min ? max : min + 1,
    median: at(0.5)
  };
}

export function positionInScale(value: number, scale: MarketScale): number {
  if (scale.max === scale.min) return 0.5;
  return (value - scale.min) / (scale.max - scale.min);
}

export function colorForValue(value: number, scale: MarketScale): string {
  return colorAt(positionInScale(value, scale));
}

/**
 * Bubble radius in SCREEN pixels, not metres.
 *
 * A metre-sized bubble vanishes at city zoom, which is exactly the zoom the
 * market map is read at. Area grows with sqrt(files) so a neighbourhood with
 * four times the inventory reads as four times the area rather than four times
 * the radius.
 */
export function bubbleRadius(files: number, maxFiles: number): number {
  if (maxFiles <= 0) return 6;
  const ratio = Math.min(1, Math.max(0, files / maxFiles));
  return 5 + 13 * Math.sqrt(ratio);
}

/** Legend tick labels: the two ends of the ramp plus the middle. */
export function legendTicks(scale: MarketScale, format: (value: number) => string) {
  return {
    low: format(scale.min),
    mid: scale.median === null ? null : format(scale.median),
    high: format(scale.max)
  };
}

/**
 * Which side of its neighbourhood's market one listing's price sits on.
 *
 * The comparison the properties page marks on every card: the listing's own
 * price per square metre against the median the AVM page draws for its
 * neighbourhood -- so the two pages read the same market instead of drifting.
 *
 * `BELOW` is green (an under-market ask), `ABOVE` is red. `EQUAL` and `NONE`
 * carry no mark at all: an equal price is not news, and a neighbourhood with no
 * median cannot judge a listing either.
 */
export type MarketVerdictDirection = 'BELOW' | 'ABOVE' | 'EQUAL' | 'NONE';

export interface MarketVerdict {
  direction: MarketVerdictDirection;
  /** Signed percent against the median; null when either side is missing. */
  deviation: number | null;
}

export function marketVerdict(
  pricePerMeter: number | null | undefined,
  neighbourhoodMedian: number | null | undefined
): MarketVerdict {
  const asked = Number(pricePerMeter);
  const median = Number(neighbourhoodMedian);
  if (
    pricePerMeter === null ||
    pricePerMeter === undefined ||
    !Number.isFinite(asked) ||
    neighbourhoodMedian === null ||
    neighbourhoodMedian === undefined ||
    !Number.isFinite(median) ||
    median <= 0
  ) {
    return { direction: 'NONE', deviation: null };
  }
  const deviation = (100 * (asked - median)) / median;
  if (deviation < 0) return { direction: 'BELOW', deviation };
  if (deviation > 0) return { direction: 'ABOVE', deviation };
  return { direction: 'EQUAL', deviation };
}

/**
 * Price per square metre of a listing, derived when the node left it null.
 *
 * A crawled row can carry a total and an area but no per-metre figure, which
 * used to render as «—» on the card and, worse, silently excluded the listing
 * from any market comparison — a listing with a price it could have been
 * priced on. The stored value always wins when present; the derivation is only
 * the fallback, never an override.
 */
export function pricePerMeterOf(property: PropertySummary): number | null {
  if (property.price_per_meter !== null) return property.price_per_meter;
  const { total_price: totalPrice, area } = property;
  if (totalPrice !== null && area !== null && area > 0) {
    return totalPrice / area;
  }
  return null;
}

/**
 * The benchmarks a listing can be judged against, per deal family.
 *
 * A sale is priced per square metre; a lease is quoted as a deposit. The two
 * families are kept apart deliberately: comparing a deposit against a price
 * per square metre is how every listing ends up "15% under market" against a
 * median it has nothing to do with.
 */
export interface MarketMedians {
  /** Median price per square metre, from the sale aggregation. */
  sale: Map<string, number>;
  /** Median deposit, from the lease aggregation. */
  rent: Map<string, number>;
}

/** Lookup key for both maps: city first, so two cities' names cannot collide. */
export function marketKey(city: string, neighborhood: string): string {
  return `${city}::${neighborhood}`;
}

/**
 * The benchmark for one listing, in the unit the listing itself is quoted in.
 *
 * Picked by deal family, so a sale reads the sale medians and a lease the lease
 * medians. A neighbourhood the node has too few files in returns null, and the
 * card shows no verdict rather than a median it does not have.
 */
export function marketMedianFor(
  property: PropertySummary,
  medians: MarketMedians
): number | null {
  const key = marketKey(property.city, property.neighborhood);
  const map = property.deal_type === 'SALE' ? medians.sale : medians.rent;
  return map.get(key) ?? null;
}

/**
 * The figure of a listing expressed in its benchmark's unit.
 *
 * Price per square metre for a sale — derived when the node left it null — and
 * the deposit for a lease. Null when the node holds no such number, which is
 * the honest answer for a lease quoted only as a monthly rent.
 */
export function comparablePriceOf(property: PropertySummary): number | null {
  if (property.deal_type === 'SALE') return pricePerMeterOf(property);
  return property.deposit_amount;
}
