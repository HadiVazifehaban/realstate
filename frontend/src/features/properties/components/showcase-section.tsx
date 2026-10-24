'use client';

import * as React from 'react';
import { useProperties } from '../hooks';
import { useActiveCityName } from '@/store/useCityStore';
import { Separator } from '@/components/ui/separator';
import type { PropertySummary } from '../types';
import type { MarketMedians } from '../utils/market';
import { type ShowcaseVariant } from './property-card';
import { ShowcaseFilterBar, categoryTypes, type ShowcaseCategory } from './showcase-filter-bar';
import type { ShowcaseAdvancedFilters } from './advanced-filter-sheet';
import { ShowcaseRail } from './showcase-rail';

/**
 * Luxury showcase block mounted above the radar grid.
 *
 * The rails are the page's filter preview: every control in the toolbar above
 * them -- category, price, area, city, source, the bargain toggle -- is owned
 * by the radar page and applied twice, once here over the newest 120 listings
 * and once server-side over the grid below. That is what makes the toolbar a
 * page filter rather than a widget filter.
 *
 * The split is deliberate. `source` goes into this window's own query, because
 * a client-side pass over the newest 120 would starve the rails whenever those
 * 120 all come from one portal. Category, price and area are applied here
 * client-side over the same window -- the list endpoint takes their bounds
 * too, but the page already carries them, so the rails never wait on a
 * response the grid's own request will make anyway.
 */

const WINDOW = 120;

export interface ShowcaseGlobalFilters {
  city?: string;
  source?: string;
}

export function ShowcaseSection({
  category,
  onCategory,
  priceB,
  onPriceB,
  area,
  onArea,
  globalSource,
  onGlobalSource,
  bargainOnly,
  onBargainOnly,
  sourceOptions,
  sourceLabels,
  onRefresh,
  refreshing,
  advanced,
  onAdvanced,
  onOpenAdvanced,
  dealTypes,
  onDealTypes,
  marketMedians
}: {
  category: ShowcaseCategory;
  onCategory: (category: ShowcaseCategory) => void;
  /** Price bounds in billions of tomans; `[0, 20]` means unbounded. */
  priceB: [number, number];
  onPriceB: (range: [number, number]) => void;
  /** Area bounds in m²; `[0, 500]` means unbounded. */
  area: [number, number];
  onArea: (range: [number, number]) => void;
  globalSource?: string;
  onGlobalSource?: (source: string | undefined) => void;
  /** Quick "only under-priced units" toggle, owned by the page (grid-scoped). */
  bargainOnly?: boolean;
  onBargainOnly?: (next: boolean) => void;
  sourceOptions?: readonly string[];
  sourceLabels?: Record<string, string>;
  onRefresh?: () => void;
  refreshing?: boolean;
  /** Detailed attribute filters, owned by the page and shared with the grid. */
  advanced: ShowcaseAdvancedFilters;
  onAdvanced: (next: ShowcaseAdvancedFilters) => void;
  onOpenAdvanced?: () => void;
  /** Applied deal families; empty means both are in scope. */
  dealTypes: string[];
  onDealTypes: (next: string[]) => void;
  /** Benchmarks for both deal families, so a rail's lease cards are marked too. */
  marketMedians?: MarketMedians;
}) {
  // پل City Gate: شهر فعال سراسری برای showcase
  const gateCity = useActiveCityName();
  const cities = gateCity ? [gateCity] : [];

  // The source pill is page state, so it has to reach the rails' window too.
  // Client-side filtering of a 120-row window would starve the rails the moment
  // the office's newest 120 all come from one portal -- filtering server-side
  // fills the window with the picked source's own newest listings instead.
  /*
    The deal axis is part of the window query, not a client-side pass: the
    newest 120 rows may hold a handful of leases, so filtering them in the
    browser would show an almost-empty lease rail while thousands of leases sit
    just below the window.
  */
  const { data, isPending, isError } = useProperties({
    limit: WINDOW,
    offset: 0,
    source: globalSource,
    deal_type: dealTypes.length ? dealTypes : undefined,
    // The market belongs in the window query for the same reason `source` does:
    // a client-side pass over 120 rows would hide a city whose newest listing
    // is 24 hours old, which is exactly the file a desk wants to see first.
    city: cities.length ? cities : undefined
  });
  const items = data?.items ?? [];

  const filtered = React.useMemo(
    () => applyShowcaseFilters(items, { category, priceB, area, cities }),
    [items, category, priceB, area, cities]
  );
  const buy = React.useMemo(() => filtered.filter((p) => p.deal_type === 'SALE'), [filtered]);
  const rent = React.useMemo(
    () => filtered.filter((p) => p.deal_type === 'RENT' || p.deal_type === 'FULL_MORTGAGE'),
    [filtered]
  );

  /**
   * «فروش» only admits SALE, so the lease rail must not render at all.
   *
   * Derived from the applied list rather than from `rent.length === 0`, because
   * a lease rail that is empty *because nothing is registered yet* still
   * deserves its own "nothing yet" message — the two cases mean opposite
   * things to an advisor reading the page.
   */
  const leaseInScope = dealTypes.length === 0 || dealTypes.some((d) => d !== 'SALE');
  const saleInScope = dealTypes.length === 0 || dealTypes.includes('SALE');

  return (
    <div className='flex flex-col gap-6'>
      <ShowcaseFilterBar
        category={category}
        onCategory={onCategory}
        priceB={priceB}
        onPriceB={onPriceB}
        area={area}
        onArea={onArea}
        globalSource={globalSource}
        onGlobalSource={onGlobalSource}
        bargainOnly={bargainOnly}
        onBargainOnly={onBargainOnly}
        sourceOptions={sourceOptions}
        sourceLabels={sourceLabels}
        onRefresh={onRefresh}
        refreshing={refreshing}
        advanced={advanced}
        onAdvanced={onAdvanced}
        onOpenAdvanced={onOpenAdvanced}
        dealTypes={dealTypes}
        onDealTypes={onDealTypes}
      />
      {/*
        Same reasoning for the sale rail: «رهن کامل» or «رهن و اجاره» rules it
        out, so it is dropped rather than left as an empty box.
      */}
      {saleInScope && (
        <>
          <ShowcaseRail
            title='ویترین خرید'
            subtitle='فروش · منتخب مشاوران'
            variant='buy'
            items={buy}
            total={buy.length}
            loading={isPending}
            viewAllHref='/dashboard/properties?deal=SALE'
            marketMedians={marketMedians}
          />
          {leaseInScope && <Separator className='my-4' />}
        </>
      )}
      {/*
        The lease rail is dropped when the deal axis excludes leases rather
        than left showing "nothing is registered yet" — that message would say
        the office holds no rentals when the truth is the filter just ruled
        them out. While the window is still in flight it stays up, so the
        skeletons do not flash away and back.
      */}
      {(!isPending && !isError) && leaseInScope && (
        <ShowcaseRail
          title='ویترین اجاره'
          subtitle='رهن و اجاره · منتخب مشاوران'
          variant='rent'
          items={rent}
          total={rent.length}
          loading={false}
          viewAllHref='/dashboard/properties?deal=RENT'
          marketMedians={marketMedians}
        />
      )}
    </div>
  );
}

interface ShowcaseFilters {
  category: ShowcaseCategory;
  priceB: [number, number];
  area: [number, number];
  /** Applied market; empty means every city is in scope. */
  cities: string[];
}

const BILLION = 1_000_000_000;

/** Price relevant to the deal: total for sale, deposit-then-rent for leases. */
function priceOf(p: PropertySummary, variant: ShowcaseVariant): number | null {
  if (variant === 'rent') return p.deposit_amount ?? p.monthly_rent;
  return p.total_price;
}

/**
 * The showcase variant a listing belongs to: a sale, or a lease.
 *
 * Shared by the rails and the bottom grid so the two cannot disagree about
 * which price block a card shows -- the grid does not know which rail a row
 * came from, so it derives the same way.
 */
export function showcaseVariantOf(dealType: PropertySummary['deal_type']): ShowcaseVariant {
  return dealType === 'SALE' ? 'buy' : 'rent';
}

function variantOf(p: PropertySummary): ShowcaseVariant {
  return showcaseVariantOf(p.deal_type);
}

export function applyShowcaseFilters(items: PropertySummary[], f: ShowcaseFilters): PropertySummary[] {
  const types = categoryTypes(f.category);
  const [loB, hiB] = f.priceB;
  const [loA, hiA] = f.area;
  const priceBounded = loB > 0 || hiB < 20;
  const areaBounded = loA > 0 || hiA < 500;

  return items.filter((p) => {
    if (types && !types.includes(p.property_type)) return false;
    // An empty market means every city is in scope, exactly like an empty
    // filter anywhere else — «همهٔ شهرها», not «no city».
    if (f.cities.length && !f.cities.includes(p.city)) return false;
    if (areaBounded) {
      if (p.area === null) return false;
      if (p.area < loA || (hiA < 500 && p.area > hiA)) return false;
    }
    if (priceBounded) {
      const price = priceOf(p, variantOf(p));
      if (price === null) return false;
      if (price < loB * BILLION || (hiB < 20 && price > hiB * BILLION)) return false;
    }
    return true;
  });
}
