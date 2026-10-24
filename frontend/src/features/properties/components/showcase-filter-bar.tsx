'use client';

import * as React from 'react';
import { Icons } from '@/components/icons';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Slider } from '@/components/ui/slider';
import { cn, toPersianDigits } from '@/lib/utils';
import { SUBMITTER_TYPES } from '../types';
import type { PropertyType } from '../types';
import { CURRENT_YEAR, type ShowcaseAdvancedFilters } from './advanced-filter-sheet';

/** Quick-switch toolbar: category tabs, price/area sliders, city trigger. */
export type ShowcaseCategory = 'all' | 'residential' | 'commercial' | 'villa';

export const CATEGORY_TABS: { value: ShowcaseCategory; label: string; icon: keyof typeof Icons }[] = [
  { value: 'all', label: 'همه', icon: 'galleryVerticalEnd' },
  { value: 'residential', label: 'مسکونی', icon: 'home' },
  { value: 'commercial', label: 'تجاری و اداری', icon: 'building' },
  { value: 'villa', label: 'ویلایی و مستغلات', icon: 'amenityBalcony' }
];

const RESIDENTIAL: PropertyType[] = ['APARTMENT', 'SUITE', 'PENTHOUSE'];
const COMMERCIAL: PropertyType[] = ['OFFICE', 'STORE', 'WAREHOUSE', 'INDUSTRIAL'];
const VILLA_ESTATE: PropertyType[] = ['VILLA', 'LAND', 'GARDEN'];

export function categoryTypes(category: ShowcaseCategory): PropertyType[] | null {
  if (category === 'residential') return RESIDENTIAL;
  if (category === 'commercial') return COMMERCIAL;
  if (category === 'villa') return VILLA_ESTATE;
  return null;
}

export const PRICE_MAX_B = 20;
export const PRICE_STEP_B = 0.5;
export const AREA_MAX = 500;
export const AREA_STEP = 10;

interface ShowcaseFilterBarProps {
  category: ShowcaseCategory;
  onCategory: (category: ShowcaseCategory) => void;
  priceB: [number, number];
  onPriceB: (range: [number, number]) => void;
  area: [number, number];
  onArea: (range: [number, number]) => void;
  /** Global (server-side) source applied to the grid below. */
  globalSource?: string;
  onGlobalSource?: (source: string | undefined) => void;
  /** Quick "only under-priced units" toggle, wired to the grid below. */
  bargainOnly?: boolean;
  onBargainOnly?: (next: boolean) => void;
  /** Source options + labels for the global source switch. */
  sourceOptions?: readonly string[];
  sourceLabels?: Record<string, string>;
  /** Refetch affordance for the grid below. */
  onRefresh?: () => void;
  refreshing?: boolean;
  /** Detailed attribute filters, owned by the page so the same values drive the
   *  server query below the rails.
   *
   *  Passed in rather than held here because the chips in this bar and the
   *  drawer both write to it: two owners would mean a chip could read one state
   *  while the query used another.
   */
  advanced: ShowcaseAdvancedFilters;
  onAdvanced: (next: ShowcaseAdvancedFilters) => void;
  /** Opens the detailed-attribute drawer. */
  onOpenAdvanced?: () => void;
  /** Applied deal families; empty means both are in scope. */
  dealTypes: string[];
  onDealTypes: (next: string[]) => void;
}

/** How many detailed filters are set, for the badge on the drawer trigger. */
function countAdvanced(filters: ShowcaseAdvancedFilters): number {
  return Object.values(filters).filter((value) => value !== undefined && value !== false).length;
}

/**
 * The deal axis: sale, or lease.
 *
 * Separate from the category tabs beside it, which ask *what kind of unit* this
 * is. Collapsing the two into one control is exactly what leaves a page able to
 * filter by apartment, villa and age band but not by whether the unit is for
 * sale or for rent -- the first question any buyer asks.
 *
 * «رهن و اجاره» carries two stored deal types (RENT and FULL_MORTGAGE), because
 * a deposit-only lease is still a lease. So the bar sends a list, and «همه»
 * sends nothing at all rather than repeating every type at the node.
 */
const DEAL_CHOICES: { key: string; label: string; values: string[] }[] = [
  { key: 'all', label: 'همه', values: [] },
  { key: 'sale', label: 'فروش', values: ['SALE'] },
  { key: 'rent', label: 'رهن و اجاره', values: ['RENT', 'FULL_MORTGAGE'] },
  { key: 'mortgage', label: 'رهن کامل', values: ['FULL_MORTGAGE'] }
];

/** Which choice matches what is applied, so it renders as selected. */
function dealKeyFor(applied: readonly string[]): string {
  if (applied.length === 0) return 'all';
  const exact = DEAL_CHOICES.find(
    (choice) =>
      choice.values.length === applied.length &&
      choice.values.every((value) => applied.includes(value))
  );
  return exact?.key ?? 'all';
}

const ACTIVE_TAB = 'bg-background text-foreground shadow-xs ring-1 ring-gold-accent/50';
const IDLE_TAB = 'text-muted-foreground hover:text-foreground';

/**
 * Shared slider skin for the range tiles.
 *
 * The stock thumb is a small white pill on a hairline grey track, which reads
 * as an unthemed control next to the gold language everywhere else in the
 * showcase. Gold-filled thumb, gold range, slightly roomier track and thumb so
 * the drag target is comfortable on a phone.
 */
const SLIDER_SKIN =
  '[&_[data-slot=slider-track]]:h-1.5 ' +
  '[&_[data-slot=slider-range]]:bg-gold-accent ' +
  '[&_[data-slot=slider-thumb]]:size-4 ' +
  '[&_[data-slot=slider-thumb]]:border-2 ' +
  '[&_[data-slot=slider-thumb]]:border-gold-accent ' +
  '[&_[data-slot=slider-thumb]]:bg-gold-primary ' +
  '[&_[data-slot=slider-thumb]]:shadow-[0_2px_8px_rgba(229,168,123,0.35)] ' +
  '[&_[data-slot=slider-thumb]]:transition-transform ' +
  'hover:[&_[data-slot=slider-thumb]]:scale-110 ' +
  'active:[&_[data-slot=slider-thumb]]:scale-105';

/**
 * Sale vs. lease, as a four-way switch.
 *
 * `همه` clears the applied list rather than sending every deal type, so the
 * request carries no `deal_type` at all — which also keeps «همه» meaning
 * "no constraint" instead of a snapshot of today's enum.
 */
function DealTypeControl({
  applied,
  onChange
}: {
  applied: string[];
  onChange: (next: string[]) => void;
}) {
  const active = dealKeyFor(applied);
  return (
    <div
      className='bg-muted flex flex-wrap items-center gap-1 rounded-full p-1'
      role='tablist'
      aria-label='نوع معامله'
    >
      {DEAL_CHOICES.map((choice) => {
        const selected = active === choice.key;
        return (
          <button
            key={choice.key}
            type='button'
            role='tab'
            aria-selected={selected}
            onClick={() => onChange(choice.values)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold transition-all',
              selected ? ACTIVE_TAB : IDLE_TAB,
              selected && 'text-gold-primary'
            )}
          >
            {selected && (
              <Icons.check aria-hidden className='size-3 text-gold-dark' />
            )}
            {choice.label}
          </button>
        );
      })}
    </div>
  );
}

/**
 * A single-tap search over the desk's four (plus two) most repeated asks.
 *
 * `shrink-0` matters: the row scrolls horizontally on a phone, and a chip that
 * wraps instead of staying its own width breaks the line into a ragged two-row
 * stack that reads as a broken layout rather than a scroll container.
 */
function QuickChip({
  label,
  icon,
  active,
  onClick
}: {
  label: string;
  icon: React.ReactNode;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type='button'
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'inline-flex h-7 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 text-[11px] font-semibold transition-colors',
        active
          ? 'border-gold-accent/60 bg-gold-accent/15 text-gold-primary'
          : 'border-border bg-muted/40 text-muted-foreground hover:text-foreground hover:border-gold-accent/40'
      )}
    >
      {icon}
      {label}
    </button>
  );
}

/**
 * Normalise the slider's emitted value back into a two-bound range.
 *
 * Base UI emits the whole array for a two-thumb slider, but a single number is
 * possible, and turning that into `[v, v]` collapses the range onto itself --
 * the end thumb landing on the start one then reads as "تا ۰ میلیارد" with a
 * zero-width bar. A bare number therefore names only the bound that moved, and
 * the other one is kept from the fallback.
 */
function toRange(value: number | readonly number[], fallback: [number, number]): [number, number] {
  const arr = Array.isArray(value) ? value : [value];
  return [arr[0] ?? fallback[0], arr[1] ?? fallback[1]];
}

export function ShowcaseFilterBar(p: ShowcaseFilterBarProps) {
  // Open the advanced row as soon as any advanced filter is active, so an
  // applied price/area/city is never hidden behind a closed disclosure.
  const priceBounded = p.priceB[0] > 0 || p.priceB[1] < PRICE_MAX_B;
  const areaBounded = p.area[0] > 0 || p.area[1] < AREA_MAX;
  const hasAdvanced =
    priceBounded || areaBounded || !!p.bargainOnly;
  const [open, setOpen] = React.useState(hasAdvanced);
  React.useEffect(() => {
    if (hasAdvanced) setOpen(true);
  }, [hasAdvanced]);

  const activeCount =
    (priceBounded ? 1 : 0) +
    (areaBounded ? 1 : 0) +
    (p.bargainOnly ? 1 : 0);

  /** Detailed filters set in the drawer, shown on its trigger. */
  const advancedActiveCount = countAdvanced(p.advanced);

  function resetAdvanced() {
    p.onPriceB([0, PRICE_MAX_B]);
    p.onArea([0, AREA_MAX]);
    p.onBargainOnly?.(false);
    p.onAdvanced({});
  }

  return (
    <section aria-label='پالایش ویترین' className='bg-card text-card-foreground rounded-xl border shadow-xs'>
      {/* Category segmented control + advanced toggle on one line. */}
      <div className='flex flex-wrap items-center gap-2 p-3'>
        {/*
          The second axis of the first question: sale, or lease. Beside the
          market rather than below it, because a buyer opens the page knowing
          both before they care whether it is a maisonette or a villa.
        */}
        <DealTypeControl applied={p.dealTypes} onChange={p.onDealTypes} />

        <div
          className='bg-muted flex flex-wrap items-center gap-1 rounded-full p-1'
          role='tablist'
          aria-label='دسته‌بندی ملک'
        >
          {CATEGORY_TABS.map((tab) => {
            const active = p.category === tab.value;
            const TabIcon = Icons[tab.icon];
            return (
              <button
                key={tab.value}
                type='button'
                role='tab'
                aria-selected={active}
                onClick={() => p.onCategory(tab.value)}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold transition-all',
                  active ? ACTIVE_TAB : IDLE_TAB
                )}
              >
                <TabIcon aria-hidden className={cn('size-3.5', active && 'text-gold-dark')} />
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className='ms-auto flex items-center gap-2'>
          {activeCount > 0 && (
            <Badge variant='secondary' className='tabular-nums'>
              {toPersianDigits(activeCount.toLocaleString('en-US'))} فیلتر فعال
            </Badge>
          )}
          <Collapsible open={open} onOpenChange={setOpen}>
            <CollapsibleTrigger
              render={
                <Button variant='ghost' size='sm' className='gap-1.5'>
                  <Icons.adjustments className='size-4' aria-hidden />
                  فیلتر پیشرفته
                  <Icons.chevronDown
                    aria-hidden
                    className={cn('size-3.5 transition-transform', open && 'rotate-180')}
                  />
                </Button>
              }
            />
          </Collapsible>

          {/*
            The detailed attributes live in a drawer rather than a second row
            here. The bar already carries a category control, two sliders and a
            city picker; adding age bands, floors, amenities and source
            switches inline turned it into a form and pushed the quick chips —
            the searches a working advisor repeats all day — below the fold.
          */}
          <Button
            variant='outline'
            size='sm'
            className='gap-1.5'
            onClick={() => p.onOpenAdvanced?.()}
          >
            <Icons.adjustments className={cn("size-3.5", advancedActiveCount > 0 && "text-gold-dark")} aria-hidden />
            ویژگی‌های ملک
            {advancedActiveCount > 0 && (
              <Badge variant='secondary' className='ms-1 h-4 rounded-full px-1.5 text-[10px]'>
                {toPersianDigits(advancedActiveCount.toLocaleString('en-US'))}
              </Badge>
            )}
          </Button>
        </div>
      </div>

      {/*
        Quick chips: the four searches that are worth a single tap, kept above
        the feed where a scroll cannot hide them. Each one is a full query, not
        a cosmetic label — they set the same filter state the drawer and the
        sliders write to, so a chip and a drawer control can never disagree
        about what is applied.
      */}
      <div className='border-t px-3 py-2'>
        <div
          className='scrollbar-none -mx-1 flex gap-1.5 overflow-x-auto px-1'
          role='group'
          aria-label='فیلترهای سریع'
        >
          <QuickChip
            label='نوساز'
            icon={<Icons.add className='size-3.5' aria-hidden />}
            active={p.advanced.min_year_built === CURRENT_YEAR}
            onClick={() =>
              p.onAdvanced({
                ...p.advanced,
                min_year_built: p.advanced.min_year_built === CURRENT_YEAR ? undefined : CURRENT_YEAR
              })
            }
          />
          <QuickChip
            label='زیر قیمت'
            icon={<Icons.sparkles className='size-3.5' aria-hidden />}
            active={Boolean(p.bargainOnly)}
            onClick={() => p.onBargainOnly?.(!p.bargainOnly)}
          />
          <QuickChip
            label='مالک شخصی'
            icon={<Icons.user className='size-3.5' aria-hidden />}
            active={p.advanced.submitter_type === SUBMITTER_TYPES[0]}
            onClick={() =>
              p.onAdvanced({
                ...p.advanced,
                submitter_type:
                  p.advanced.submitter_type === SUBMITTER_TYPES[0]
                    ? undefined
                    : SUBMITTER_TYPES[0]
              })
            }
          />
          <QuickChip
            label='دارای پارکینگ'
            icon={<Icons.amenityParking className='size-3.5' aria-hidden />}
            active={Boolean(p.advanced.has_parking)}
            onClick={() => p.onAdvanced({ ...p.advanced, has_parking: !p.advanced.has_parking })}
          />
          <QuickChip
            label='۲۴ ساعت گذشته'
            icon={<Icons.calendar className='size-3.5' aria-hidden />}
            active={p.advanced.published_within_hours === 24}
            onClick={() =>
              p.onAdvanced({
                ...p.advanced,
                published_within_hours: p.advanced.published_within_hours === 24 ? undefined : 24
              })
            }
          />
          <QuickChip
            label='آسانسور'
            icon={<Icons.amenityElevator className='size-3.5' aria-hidden />}
            active={Boolean(p.advanced.has_elevator)}
            onClick={() =>
              p.onAdvanced({ ...p.advanced, has_elevator: !p.advanced.has_elevator })
            }
          />
        </div>
      </div>

      <Collapsible open={open} onOpenChange={setOpen}>
        <CollapsibleContent className='px-3 pb-3'>
          <div className='border-t pt-3'>
            <div className='grid grid-cols-1 gap-3 md:grid-cols-2'>
              <RangeCard
                icon={<Icons.trendingUp aria-hidden className='text-gold-dark size-3.5' />}
                title='بازه قیمت (تومان)'
                valueLabel={priceLabel(p.priceB)}
                slider={
                  <Slider
                    min={0}
                    max={PRICE_MAX_B}
                    step={PRICE_STEP_B}
                    value={p.priceB}
                    onValueChange={(v) => p.onPriceB(toRange(v, [0, PRICE_MAX_B]))}
                    // One step of daylight between the thumbs: without it the
                    // end thumb can be dragged onto the start one, the bar
                    // collapses to zero width and the label reads "تا ۰ میلیارد".
                    minStepsBetweenValues={1}
                    aria-label='بازه قیمت به میلیارد تومان'
                    className={SLIDER_SKIN}
                  />
                }
              />
              <RangeCard
                icon={<Icons.statArea aria-hidden className='text-gold-dark size-3.5' />}
                title='متراژ (متر مربع)'
                valueLabel={areaLabel(p.area)}
                slider={
                  <Slider
                    min={0}
                    max={AREA_MAX}
                    step={AREA_STEP}
                    value={p.area}
                    onValueChange={(v) => p.onArea(toRange(v, [0, AREA_MAX]))}
                    minStepsBetweenValues={1}
                    aria-label='بازه متراژ'
                    className={SLIDER_SKIN}
                  />
                }
              />
            </div>
            <div className='mt-3 flex flex-wrap items-center gap-2 border-t pt-3'>
              {/* Quick hunt: only under-priced units (grid below). */}
              {p.onBargainOnly && (
                <Button
                  variant='outline'
                  size='sm'
                  aria-pressed={!!p.bargainOnly}
                  onClick={() => p.onBargainOnly?.(!p.bargainOnly)}
                  className={cn(
                    'h-7 gap-1.5 rounded-full px-3 text-xs font-semibold',
                    p.bargainOnly &&
                      'border-gold-accent/60 bg-gold-accent/15 text-gold-dark shadow-[0_0_14px_rgba(229,168,123,0.25)]'
                  )}
                >
                  <Icons.adjustments aria-hidden className='size-3.5' />
                  فقط شکار قیمت
                </Button>
              )}
              {hasAdvanced && (
                <Button variant='ghost' size='sm' onClick={resetAdvanced} className='gap-1.5'>
                  <Icons.close className='size-3.5' aria-hidden />
                  پاک‌سازی فیلترها
                </Button>
              )}
            </div>
            {p.sourceOptions && p.onGlobalSource && (
              <GlobalSourceRow
                options={p.sourceOptions}
                labels={p.sourceLabels ?? {}}
                value={p.globalSource}
                onChange={p.onGlobalSource}
                onRefresh={p.onRefresh}
                refreshing={p.refreshing}
              />
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
}

/**
 * Server-side source switch for the grid below, rendered inside the advanced
 * panel so all filters live in one toolbar.
 *
 * A segmented pill group (same language as the category switch above): the
 * active source reads as one filled pill, the rest as quiet text buttons.
 * The refresh affordance sits at the row end so the grid's refetch no longer
 * needs its own orphaned button row on the page.
 */
function GlobalSourceRow({
  options,
  labels,
  value,
  onChange,
  onRefresh,
  refreshing
}: {
  options: readonly string[];
  labels: Record<string, string>;
  value?: string;
  onChange: (source: string | undefined) => void;
  onRefresh?: () => void;
  refreshing?: boolean;
}) {
  return (
    <div className='mt-3 flex flex-wrap items-center gap-2 border-t pt-3'>
      <span className='text-muted-foreground inline-flex items-center gap-1.5 text-xs font-semibold'>
        <Icons.galleryVerticalEnd aria-hidden className='text-gold-dark size-3.5' />
        منبع آگهی:
      </span>
      <div className='bg-muted flex flex-wrap items-center gap-1 rounded-full p-1' role='group' aria-label='منبع آگهی'>
        <button
          type='button'
          aria-pressed={!value}
          onClick={() => onChange(undefined)}
          className={cn(
            'rounded-full px-3 py-1 text-xs font-semibold transition-all',
            !value ? 'bg-background text-foreground shadow-xs ring-1 ring-gold-accent/50' : 'text-muted-foreground hover:text-foreground'
          )}
        >
          همه
        </button>
        {options.map((source) => {
          const active = value === source;
          return (
            <button
              key={source}
              type='button'
              aria-pressed={active}
              onClick={() => onChange(active ? undefined : source)}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-semibold transition-all',
                active
                  ? 'bg-background text-foreground shadow-xs ring-1 ring-gold-accent/50'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {labels[source] ?? source}
            </button>
          );
        })}
      </div>
      {onRefresh && (
        <Button
          variant='outline'
          size='sm'
          onClick={onRefresh}
          disabled={refreshing}
          className='ms-auto gap-1.5'
        >
          <Icons.refresh aria-hidden className={cn('size-3.5', refreshing && 'animate-spin')} />
          {refreshing ? 'در حال به‌روزرسانی…' : 'به‌روزرسانی'}
        </Button>
      )}
    </div>
  );
}

/** One range filter tile: icon + title, live value, slider. */
function RangeCard({
  icon,
  title,
  valueLabel,
  slider
}: {
  icon: React.ReactNode;
  title: string;
  valueLabel: string;
  slider: React.ReactNode;
}) {
  return (
    <div className='bg-muted/50 flex flex-col gap-2.5 rounded-lg border p-3'>
      <div className='flex items-center justify-between text-xs'>
        <span className='text-foreground inline-flex items-center gap-1.5 font-semibold'>
          {icon}
          {title}
        </span>
        <span className='text-muted-foreground tabular-nums'>{valueLabel}</span>
      </div>
      {slider}
    </div>
  );
}

/** '۲ تا ۵ میلیارد' / 'بدون محدودیت' -- a range the advisor can read at a glance. */
function priceLabel(range: [number, number]): string {
  const [lo, hi] = range;
  if (lo === 0 && hi === PRICE_MAX_B) return 'بدون محدودیت';
  const fmt = (v: number) => toPersianDigits(v.toLocaleString('en-US', { maximumFractionDigits: 1 }));
  if (lo === 0) return `تا ${fmt(hi)} میلیارد`;
  if (hi === PRICE_MAX_B) return `از ${fmt(lo)} میلیارد`;
  return `${fmt(lo)} تا ${fmt(hi)} میلیارد`;
}

function areaLabel(range: [number, number]): string {
  const [lo, hi] = range;
  if (lo === 0 && hi === AREA_MAX) return 'بدون محدودیت';
  const fmt = (v: number) => toPersianDigits(v.toLocaleString('en-US'));
  if (lo === 0) return `تا ${fmt(hi)} متر`;
  if (hi === AREA_MAX) return `از ${fmt(lo)} متر`;
  return `${fmt(lo)} تا ${fmt(hi)} متر`;
}
