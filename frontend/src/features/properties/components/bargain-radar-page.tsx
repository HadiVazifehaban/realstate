'use client';

import * as React from 'react';
import { Icons } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { toPersianDigits } from '@/lib/utils';
import { useMarketMedians, useProperties } from '../hooks';
import type { PropertyListFilters } from '../api/client';
import { PropertyCard } from './property-card';
import { AddToLeadsButton } from './add-to-leads-button';
import { ShowcaseSection } from './showcase-section';
import { CrawlThisMarket } from './crawl-this-market';
import { EmptyMarketCollector } from './empty-market-collector';
import {
  AdvancedFilterSheet,
  type ShowcaseAdvancedFilters
} from './advanced-filter-sheet';
import { categoryTypes, type ShowcaseCategory } from './showcase-filter-bar';
import { SOURCE_LABELS } from '../utils/labels';
import { marketMedianFor } from '../utils/market';
import { useQueryStates } from 'nuqs';
import { parseAsArrayOf, parseAsString } from 'nuqs';

/**
 * Rows the first render carries, and how many each "نمایش بیشتر" click adds.
 *
 * The feed pages by growing the window rather than by offset: page 2 is the
 * same query with a bigger `limit`, so nothing already on screen moves under
 * the reader's finger, and the grid keeps its scroll position between loads.
 *
 * `MAX_LIMIT` mirrors the API's own `le=2500` cap. Past it the request would
 * be rejected, so the button retires instead of becoming a dead click -- the
 * office's remaining inventory then only reads by narrowing a filter.
 */
const PAGE_SIZE = 1000;
const LOAD_MORE_STEP = 1000;
const MAX_LIMIT = 2500;

/**
 * Source filter values.
 *
 * These are the canonical `PropertySource` members, matching `SOURCE_LABELS`.
 * The API expands a canonical value back out to every legacy spelling that
 * folds onto it, so sending 'DIVAR' still returns the rows stored as
 * DIVAR_SCRAPER -- which on this node is all of them.
 */
const SOURCE_OPTIONS = ['DIVAR', 'DELTA', 'SHEYPOOR', 'INTERNAL_AGENCY', 'INTERNAL_USER'] as const;

/**
 * Slider bounds, mirrored from the showcase toolbar's constants.
 *
 * A range sitting on the bound counts as *unbounded* and is dropped from the
 * query, so the default `[0, 20]` / `[0, 500]` state sends no range at all --
 * exactly as the client-side showcase filter already treats it.
 */
const PRICE_MAX_B = 20;
const AREA_MAX = 500;
const BILLION = 1_000_000_000;

/**
 * Read the applied market back out of the filter state as a list of cities.
 *
 * `filters.city` is a ``string | string[]`` because a market is rarely one
 * city: a Tehran desk works the capital and its satellites. Tolerating a bare
 * string keeps a market restored from an old URL or a persisted filter still
 * working.
 */
function normalizeCities(city: string | string[] | undefined): string[] {
  if (!city) return [];
  const raw = Array.isArray(city) ? city : [city];
  return Array.from(new Set(raw.map((entry) => entry.trim()).filter(Boolean)));
}

/**
 * Live inventory feed for the office node.
 *
 * Backed by ``GET /api/v1/properties`` (crawled + first-party listings) rather
 * than the valuation-gated radar, so a freshly scraped unit shows up the moment
 * it lands. Under-priced units are highlighted and sorted to the front, which
 * keeps the 'bargain radar' promise without dead-ending on an empty feed while
 * the AVM is still gathering comparables.
 */
export default function BargainRadarPage() {
  // The showcase toolbar's filter state lives HERE, not in the rails widget:
  // every control in it filters the whole page, so the same values drive the
  // grid query below and the rails above. Keeping them in one place is what
  // stops the two from drifting apart.
  const [category, setCategory] = React.useState<ShowcaseCategory>('all');
  const [priceB, setPriceB] = React.useState<[number, number]>([0, PRICE_MAX_B]);
  const [area, setArea] = React.useState<[number, number]>([0, AREA_MAX]);
  
  // URL state for cities (syncs with header location picker)
  const [cityParams] = useQueryStates({
    city: parseAsArrayOf(parseAsString).withDefault([])
  });

  // URL state for search query
  const [searchParams] = useQueryStates({
    search: parseAsString.withDefault('')
  });

  const [filters, setFilters] = React.useState<PropertyListFilters>({
    limit: PAGE_SIZE,
    offset: 0
  });
  /** Quick toggle: only under-priced units (the valuation gate's bargain rows). */
  const [bargainsOnly, setBargainsOnly] = React.useState(false);

  /**
   * Detailed attribute filters (bedrooms, age, floor, amenities, radar
   * threshold, source, recency), owned here because they drive the grid's
   * server query and are written by both the quick chips and the drawer.
   *
   * Kept one flat object rather than a piece per control: every control in the
   * bar and every chip above the feed write to the same shape, so resetting
   * («پاک کردن همه») and resetting-paging can each be one statement instead of
   * a list of setters that can drift out of step.
   */
  const [advanced, setAdvanced] = React.useState<ShowcaseAdvancedFilters>({});
  const [advancedOpen, setAdvancedOpen] = React.useState(false);

   /**
    * The applied market, as a flat list of cities.
    *
    * Provinces are expanded here rather than stored: the node filters on
    * ``Property.city``, so a province reaching the query would match nothing.
    * Kept in `filters` so a market change resets the page like any other filter.
    */
   const cities = React.useMemo(
     () => normalizeCities(filters.city),
     [filters.city]
   );
   const setCities = React.useCallback(
     (next: string[]) => {
       setFilters((prev) => ({ ...prev, city: next, offset: 0, neighborhood: undefined }));
     },
     [setFilters]
   );

   /**
    * پل City Gate شکارچی: شهر فعال سراسری به‌صورت خودکار وارد فیلتر این صفحه
    * می‌شود. کاربر همچنان می‌تواند از تولبار شهر را عوض کند (فیلتر دستی
    * اولویت دارد)؛ ولی وقتی دستی چیزی انتخاب نشده، شهر گیت اعمال می‌شود تا
    * صفحه هیچ‌وقت بدون فیلتر شهر — یعنی کل کشور — کوئری نخورد.
    */
   const effectiveCities = cityParams.city;
   const citySelected = true; // An empty location means the whole country.

  /**
   * Applied deal families; empty means both are in scope.
   *
   * A list because «رهن و اجاره» is one choice in the advisor's vocabulary and
   * two stored deal types (RENT, FULL_MORTGAGE) — sending only RENT would hide
   * every deposit-only lease from the page the moment someone picked the lease
   * family.
   */
  const [dealTypes, setDealTypes] = React.useState<string[]>([]);

  /**
   * The AVM page's medians for *both* deal families, keyed by
   * ``city::neighborhood``.
   *
   * The same aggregation «تحلیل بازار» maps, fetched once here and handed to
   * both the showcase rails and the grid below, so every listing on the page is
   * judged against the market it would be priced on. React Query de-dupes each
   * call, so the page pays one request per family no matter how many cards
   * consume it.
   *
   * Both families matter: most of the node's book is *leases*, and a lease has
   * no price per square metre to mark. Judging those against the sale medians
   * would mark every lease in the city on a number that does not apply to it,
   * so `marketMedianFor` picks the family the listing itself is quoted in.
   *
   * No city filter: the marks are looked up per listing and the rails filter
   * by city on the client, so the map has to cover every city the node holds.
   * `min_files` matches the market page's own default so the two screens agree
   * on which neighbourhoods have a market.
   */
  const { medians: marketMedians } = useMarketMedians();

  const query = React.useMemo<PropertyListFilters>(() => {
    const [loB, hiB] = priceB;
    const [loA, hiA] = area;
    // The quick toggle is the valuation gate's own bargain flag; the drawer's
    // `below_market_pct` is the stronger, percentage-based reading of the same
    // radar. A percentage wins when both are set: "at least 10% under" is a
    // strictly narrower ask than "is a bargain", and sending both would let the
    // wider gate silently widen the narrower one.
    const radar = advanced.below_market_pct;
    return {
      ...filters,
      ...advanced,
      city: effectiveCities.length > 0 ? effectiveCities : undefined,
      property_type: categoryTypes(category) ?? undefined,
      min_price: loB > 0 ? Math.round(loB * BILLION) : undefined,
      max_price: hiB < PRICE_MAX_B ? Math.round(hiB * BILLION) : undefined,
      min_area: loA > 0 ? loA : undefined,
      max_area: hiA < AREA_MAX ? hiA : undefined,
      valuation_status: radar === undefined && bargainsOnly ? 'BARGAIN' : undefined,
      below_market_pct: radar,
      // Nothing at all when «همه» is picked, so the request states no
      // constraint rather than enumerating today's enum.
      deal_type: dealTypes.length ? dealTypes : undefined,
      // Search query from URL
      q: searchParams.search || undefined
    };
  }, [category, priceB, area, filters, advanced, bargainsOnly, dealTypes, effectiveCities, searchParams.search]);

  // The query must always occupy the same hook slot, including while the
  // persisted city is hydrating. Disable fetching, not the hook itself.
  const result = useProperties(query, citySelected);
  const data = citySelected ? result.data : undefined;
  const isPending = citySelected && result.isPending;
  const isError = citySelected && result.isError;
  const error = citySelected ? result.error : null;
  const refetch = result.refetch;
  const isFetching = citySelected && result.isFetching;

  // `valuation_status` is a *client* property of the row (the API's
  // `bargain_only` filter also narrows on valuation *samples*, which this
  // feed does not request), so the quick toggle is applied client-side.
  const feed = React.useMemo(() => data?.items ?? [], [data]);
  const properties = React.useMemo(() => {
    // Bargains first, then everything else in the node's natural order.
    return [...feed].sort((a, b) => {
      const aBargain = a.valuation_status === 'BARGAIN' ? 0 : 1;
      const bBargain = b.valuation_status === 'BARGAIN' ? 0 : 1;
      return aBargain - bBargain;
    });
  }, [feed]);
  const visible = React.useMemo(
    () => (bargainsOnly ? properties.filter((p) => p.valuation_status === 'BARGAIN') : properties),
    [bargainsOnly, properties]
  );

  const total = data?.count ?? 0;
  // Rows actually in hand. `total` is the server's count for the current
  // filters, so the gap between the two is exactly what "نمایش بیشتر" promises.
  const loaded = feed.length;
  const limit = filters.limit ?? PAGE_SIZE;
  const hasMore = loaded > 0 && loaded < total && limit < MAX_LIMIT;
   // Any toolbar change resets paging: staying on page 7 of a 3-page result set
   // reads as an empty grid, which is the bug this avoids. The window collapses
   // back to the first batch for the same reason.
   function withFilterReset<T>(apply: (next: T) => void) {
     return (next: T) => {
       apply(next);
       setFilters((prev) => ({ ...prev, limit: PAGE_SIZE, offset: 0 }));
     };
   }

   // Grow the window by one batch; the same rows stay where they are.
   function showMore() {
     setFilters((prev) => ({ ...prev, offset: 0, limit: (prev.limit ?? PAGE_SIZE) + LOAD_MORE_STEP }));
   }

   return (
    <div className='flex min-w-0 flex-1 flex-col gap-4 px-4 pt-2 pb-4 md:px-6 md:pt-4'>
      <div className='flex flex-col gap-4'>
          {/*
            One toolbar, whole-page scope. Everything the showcase filter bar
            owns -- category, price, area, source and the bargain toggle --
            is page state passed down from here, and the same values drive the
            server-side query the grid below is built on. There is deliberately no
            second filter row on this page.
          */}
          <ShowcaseSection
            category={category}
            onCategory={withFilterReset(setCategory)}
            priceB={priceB}
            onPriceB={withFilterReset(setPriceB)}
            area={area}
            onArea={withFilterReset(setArea)}
            globalSource={filters.source}
            onGlobalSource={(source) => setFilters((prev) => ({ ...prev, source, offset: 0 }))}
            bargainOnly={bargainsOnly}
            onBargainOnly={setBargainsOnly}
            marketMedians={marketMedians}
            advanced={advanced}
            onAdvanced={(next) => {
              setAdvanced(next);
              // A narrower filter set can outrun the loaded window, so the
              // window collapses with it — the same reset the toolbar triggers.
              setFilters((prev) => ({ ...prev, offset: 0 }));
            }}
            onOpenAdvanced={() => setAdvancedOpen(true)}
            dealTypes={dealTypes}
            onDealTypes={withFilterReset(setDealTypes)}
            sourceOptions={SOURCE_OPTIONS}
            sourceLabels={SOURCE_LABELS}
            onRefresh={() => void refetch()}
            refreshing={isFetching}
          />

          <AdvancedFilterSheet
            open={advancedOpen}
            onOpenChange={setAdvancedOpen}
            value={advanced}
            onChange={setAdvanced}
            /* One owner for `source`: the bar's select and the drawer's chips
               both write `filters.source`, so neither can out-vote the other. */
            source={filters.source}
            onSource={(next) =>
              setFilters((prev) => ({ ...prev, source: next, offset: 0, neighborhood: undefined }))
            }
          />
          <Separator />
          {cities.length > 0 && (
            <div className='flex flex-wrap items-center gap-2'>
              {cities.map((city) => (
                <span
                  key={city}
                  className='border-border bg-muted/60 text-foreground inline-flex h-8 items-center gap-1.5 rounded-md border px-2 text-xs'
                >
                  <Icons.mapPin className='text-gold-accent size-3.5' aria-hidden />
                  {city}
                  <button
                    type='button'
                    onClick={() => setCities(cities.filter((entry) => entry !== city))}
                    aria-label={`حذف فیلتر شهر ${city}`}
                    className='text-muted-foreground hover:text-foreground transition-colors'
                  >
                    <Icons.close className='size-3.5' aria-hidden />
                  </button>
                </span>
              ))}

              {/*
                Feed the market back to the scrapers.
                The filter says which city the advisor is working right now, so
                the node's next sweep should cover exactly that rather than
                whatever ``SCRAPER_CITIES`` happens to be set to.
              */}
              <CrawlThisMarket cities={cities} />

              <Button
                variant='ghost'
                size='sm'
                className='h-8'
                onClick={() => setCities([])}
              >
                <Icons.close className='size-3.5' aria-hidden />
                پاک کردن بازار
              </Button>
            </div>
          )}

          {isPending && (
            <Card>
              <CardContent className='text-muted-foreground py-10 text-center'>
                در حال دریافت آگهی‌ها…
              </CardContent>
            </Card>
          )}

          {isError && (
            <Card className='border-destructive/40'>
              <CardContent className='flex flex-col items-center gap-2 py-10 text-center'>
                <Icons.warning className='text-destructive size-6' />
                <p className='text-sm font-medium'>دریافت آگهی‌ها ناموفق بود.</p>
                <p className='text-muted-foreground text-xs'>{error?.message}</p>
              </CardContent>
            </Card>
          )}

          <EmptyMarketCollector cities={effectiveCities} empty={!isPending && !isError && total === 0} />
          {!isPending && !isError && visible.length === 0 && (
            <Card>
              <CardContent className='flex flex-col items-center gap-2 py-10 text-center'>
                <Icons.inbox className='text-muted-foreground size-6' />
                <p className='text-sm'>
                  {bargainsOnly
                    ? 'در این صفحه آگهی زیرقیمتی یافت نشد.'
                    : 'هنوز آگهی‌ای در این محدوده ثبت نشده است.'}
                </p>
                <p className='text-muted-foreground max-w-md text-xs'>
                  {bargainsOnly
                    ? `تا این لحظه ${toPersianDigits(loaded.toLocaleString('en-US'))} آگهی بررسی شده و هیچ‌کدام زیرقیمت نیستند؛ با «نمایش بیشتر» batch بعدی را هم ببینید یا فیلتر منبع را تغییر دهید.`
                    : 'برای این فیلترها آگهی ذخیره‌شده‌ای پیدا نشد؛ وضعیت جمع‌آوری خودکار شهر انتخاب‌شده در بالا نمایش داده می‌شود.'}
                </p>
              </CardContent>
            </Card>
          )}

          {visible.length > 0 ? (
            <>
              <Separator />
              {/* Grid label: mirrors the header's quick-toggle state. */}
              <div className='min-w-0'>
                <h3 className='lux-section-title'>
                  {bargainsOnly ? 'شکار قیمت' : 'کل آگهی‌ها'}
                  <span className='rounded-full border border-[rgba(229,168,123,0.3)] bg-[rgba(229,168,123,0.08)] px-2.5 py-0.5 text-[11px] font-semibold tabular-nums text-gold-primary'>
                    {toPersianDigits(total.toLocaleString('en-US'))}
                  </span>
                </h3>
                <p className='mt-1 truncate text-xs text-[#94a3b8]'>
                  {bargainsOnly
                  ? 'آگهی‌های زیرقیمت شناسایی‌شده'
                  : 'همه آگهی‌های ثبت‌شده در دفتر'}
                </p>
              </div>

              {/* Six listings per row at `xl` and up, aligned to the inline start
                   (right edge in this RTL layout, i.e. against the sidebar) rather
                   than centred: no `mx-auto` cap, the grid fills the page width and
                   the first card sits at the start edge. */}
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
                {visible.map((property, i) => (
                  <PropertyCard
                    key={property.id}
                    property={property}
                    variant={property.deal_type === 'SALE' ? 'buy' : 'rent'}
                    index={i}
                    marketMedian={marketMedianFor(property, marketMedians)}
                    leadAction={<AddToLeadsButton property={property} />}
                  />
                ))}
              </div>

              {/*
                "آگهی‌های بیشتر" instead of page numbers: the window grows by a
                batch, so everything already on screen stays exactly where it is
                and the scroll position survives the load. No counter line -- the
                grid above already says how much of the office inventory is
                showing, and a second number here just repeated it. When the
                window is exhausted the button retires rather than promising a
                batch the API's limit would refuse.
              */}
              {(hasMore || loaded >= total) && loaded > 0 && (
                <>
                  <Separator />
                  <div className='flex flex-col items-center gap-2'>
                    {hasMore ? (
                      <Button
                        variant='outline'
                        size='sm'
                        disabled={isFetching}
                        onClick={showMore}
                        className='group/more h-9 gap-2 rounded-full border-gold-accent/35 bg-gold-accent/10 px-5 text-sm font-semibold text-gold-primary shadow-[0_2px_14px_rgba(229,168,123,0.12)] transition-all duration-300 hover:-translate-y-0.5 hover:border-gold-accent/60 hover:bg-gold-accent/20 hover:shadow-[0_6px_28px_rgba(229,168,123,0.25)] active:translate-y-0'
                      >
                        {isFetching ? (
                          <Icons.spinner className='size-4 animate-spin' aria-hidden />
                        ) : (
                          <Icons.chevronDown
                            className='size-4 transition-transform duration-300 group-hover/more:translate-y-0.5'
                            aria-hidden
                          />
                        )}
                        آگهی‌های بیشتر
                      </Button>
                    ) : (
                      <p className='text-muted-foreground text-xs'>
                        {loaded >= total
                          ? 'همهٔ آگهی‌های این فیلتر نمایش داده شد.'
                          : 'برای دیدن بقیه، یک فیلتر را محدودتر کنید.'}
                      </p>
                    )}
                  </div>
                </>
              )}
            </>
          ) : (
            <div className='flex flex-col items-center gap-3 py-12 text-center'>
              <Icons.inbox className='size-8 text-muted-foreground' aria-hidden />
              <div>
                <h3 className='text-lg font-semibold'>هنوز آگهی‌ای در این محدوده ثبت نشده است</h3>
                <p className='text-muted-foreground text-sm'>
                  {total > 0
                    ? `تعداد آگهی‌های کل در دفتر: ${toPersianDigits(total.toLocaleString('en-US'))}؛ این بخش هنوز خالی است.`
                    : 'برای محدوده و فیلترهای انتخاب‌شده آگهی ذخیره‌شده‌ای پیدا نشد؛ برای دیدن موجودی سایر مناطق، شهر یا فیلترها را تغییر دهید.'}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
  );
}
