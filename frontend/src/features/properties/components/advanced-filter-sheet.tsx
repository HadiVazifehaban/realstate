'use client';

import * as React from 'react';
import { Icons } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { NativeSelect } from '@/components/ui/native-select';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle
} from '@/components/ui/sheet';
import { SOURCE_LABELS, SUBMITTER_LABELS } from '../utils/labels';
import { PROPERTY_SOURCES, SUBMITTER_TYPES } from '../types';
import type { PropertySource, SubmitterType } from '../types';

/**
 * The advanced filter drawer for the Shekarchi desk.
 *
 * Split out of the toolbar on purpose: the quick chips above the feed carry the
 * four searches a working advisor repeats all day («نوساز»، «زیر قیمت»،
 * «مالک»، «۲۴ ساعت»), while everything here is a narrowing you set once and
 * leave alone. Rendering all of it inline turned the showcase bar into a second
 * form and buried the chips under it.
 *
 * **Only what the node can actually filter is offered.** Every control here
 * maps to a query parameter on ``GET /api/v1/properties`` (see
 * ``app/api/v1/endpoints/properties.py``). Three things the brief asks for are
 * deliberately absent because the schema has nowhere to store them:
 *
 * * a dedicated/shared parking split -- the node records one bool per amenity;
 * * a one-page deed (تک‌برگ / ششدانگ) switch -- ``Property`` has no document
 *   field, so the chip would filter nothing;
 * * a verified-visit switch -- a booking is not a verified listing either.
 *
 * Left out rather than faked: a checkbox that narrows nothing is worse than a
 * missing one, and this is a desk tool.
 *
 * ``source`` is *not* part of ``ShowcaseAdvancedFilters`` even though the drawer
 * offers it. The bar already carries a source select writing the same query
 * param, and two owners of one param means a pick in one control leaves the
 * other displaying a value the query no longer uses — so it comes in here as its
 * own prop and both controls write the page's single piece of source state.
 */

export interface ShowcaseAdvancedFilters {
  /** Inclusive bedroom bounds. `max_rooms` stays unset for «4+». */
  min_rooms?: number;
  max_rooms?: number;
  min_land_area?: number;
  max_land_area?: number;
  min_price_per_meter?: number;
  max_price_per_meter?: number;
  /** Inclusive construction-year bounds; rows with no year stay unmatchable. */
  min_year_built?: number;
  max_year_built?: number;
  min_floor?: number;
  max_floor?: number;
  has_parking?: boolean;
  has_elevator?: boolean;
  has_storage?: boolean;
  has_balcony?: boolean;
  /** Bargain radar: how far under the neighbourhood AVM, in percent. */
  below_market_pct?: number;
  /** Who filed it: PERSON is the owner-direct route, AGENCY the desk's own. */
  submitter_type?: string;
  /** Recency in hours since `created_at`. */
  published_within_hours?: number;
}

/**
 * "New build" means this calendar year or later.
 *
 * Exported so the quick chip above the feed and the drawer's age band read the
 * same number: two literals for one fact are exactly how the two drift apart
 * once the calendar turns.
 */
export const CURRENT_YEAR = new Date().getFullYear();

export const EMPTY_ADVANCED: ShowcaseAdvancedFilters = {};

/**
 * Building-age bands, as year bounds the node can query.
 *
 * Derived from the current year rather than hard-coded, so «نوساز» here means
 * the same thing the quick chip means: this year or later. With fixed literals
 * the two drift apart the moment the calendar turns -- the chip would ask for
 * 2026+ while the drawer still offered "نوساز = 2024".
 */
const YEAR_NOW = new Date().getFullYear();
const AGE_BANDS: { key: string; label: string; min?: number; max?: number }[] = [
  { key: 'new', label: 'نوساز (کلید نخورده)', min: YEAR_NOW },
  { key: 'under5', label: 'زیر ۵ سال', min: YEAR_NOW - 5 },
  { key: '5to10', label: '۵ تا ۱۰ سال', min: YEAR_NOW - 10, max: YEAR_NOW - 5 },
  { key: '10to15', label: '۱۰ تا ۱۵ سال', min: YEAR_NOW - 15, max: YEAR_NOW - 10 },
  { key: 'old', label: '۱۵ سال به بالا / کلنگی', max: YEAR_NOW - 15 }
];

/** Bedroom chips: «4 خواب و بیشتر» sends only a lower bound. */
const ROOM_OPTIONS: { key: string; label: string; min: number; max?: number }[] = [
  { key: '0', label: '۰ خواب (سوئیت)', min: 0, max: 0 },
  { key: '1', label: '۱ خواب', min: 1, max: 1 },
  { key: '2', label: '۲ خواب', min: 2, max: 2 },
  { key: '3', label: '۳ خواب', min: 3, max: 3 },
  { key: '4plus', label: '۴ خواب و بیشتر', min: 4 }
];

/** Recency windows, in hours. */
const PUBLISHED_WINDOWS: { value: string; label: string; hours: number }[] = [
  { value: '24', label: '۲۴ ساعت گذشته', hours: 24 },
  { value: '72', label: '۳ روز گذشته', hours: 72 },
  { value: '168', label: 'یک هفته گذشته', hours: 168 }
];

/**
 * Where the row came from, grouped the way the desk thinks about provenance.
 *
 * The two first-party channels are the ones an advisor cares about (owner
 * direct beats a desk filing, which beats a portal scrape), so they are listed
 * ahead of the portals rather than in the enum's own precedence order.
 */
const SOURCE_GROUPS: { label: string; sources: PropertySource[]; note: string }[] = [
  {
    label: 'ثبت مستقیم',
    sources: ['INTERNAL_USER', 'INTERNAL_AGENCY'],
    note: 'مالک بدون واسطه، یا فایلی که دفتر ثبت کرده.'
  },
  { label: 'شبکه همکاران', sources: ['MLS_IMPORT'], note: 'واردشده از MLS.' },
  {
    label: 'پورتال‌ها',
    sources: ['DIVAR', 'SHEYPOOR', 'DELTA'],
    note: 'خزندهٔ سامانه.'
  }
];

/** One labelled row of the drawer, so the spacing stays consistent. */
function Row({
  label,
  hint,
  children
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className='space-y-2'>
      <div>
        <Label className='text-xs font-semibold'>{label}</Label>
        {hint && <p className='text-muted-foreground mt-0.5 text-[11px] leading-relaxed'>{hint}</p>}
      </div>
      {children}
    </div>
  );
}

/** «از / تا» bounds on one line, for the numeric ranges. */
function BoundPair({
  fromValue,
  toValue,
  onFrom,
  onTo,
  fromPlaceholder,
  toPlaceholder,
  suffix
}: {
  fromValue?: number;
  toValue?: number;
  onFrom: (next: number | undefined) => void;
  onTo: (next: number | undefined) => void;
  fromPlaceholder: string;
  toPlaceholder: string;
  suffix?: string;
}) {
  const parse = (raw: string): number | undefined => {
    if (raw.trim() === '') return undefined;
    const value = Number(raw.replace(/[^\d.]/g, ''));
    return Number.isFinite(value) ? value : undefined;
  };
  return (
    <div className='flex items-center gap-2'>
      <Input
        type='text'
        inputMode='numeric'
        className='h-8 flex-1 text-xs tabular-nums'
        placeholder={fromPlaceholder}
        value={fromValue ?? ''}
        onChange={(event) => onFrom(parse(event.target.value))}
        aria-label='از'
      />
      <span className='text-muted-foreground shrink-0 text-[11px]'>تا</span>
      <Input
        type='text'
        inputMode='numeric'
        className='h-8 flex-1 text-xs tabular-nums'
        placeholder={toPlaceholder}
        value={toValue ?? ''}
        onChange={(event) => onTo(parse(event.target.value))}
        aria-label='تا'
      />
      {suffix && <span className='text-muted-foreground shrink-0 text-[11px]'>{suffix}</span>}
    </div>
  );
}

/** A chip that toggles one boolean amenity. */
function AmenityChip({
  label,
  checked,
  onToggle
}: {
  label: string;
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <label className='border-border bg-muted/40 hover:bg-muted/70 flex h-8 cursor-pointer items-center gap-2 rounded-full border px-3 text-[11px] font-medium transition-colors'>
      <Checkbox
        checked={checked}
        onCheckedChange={() => onToggle()}
        className='size-3.5'
        aria-label={label}
      />
      {label}
    </label>
  );
}

interface AdvancedFilterSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  value: ShowcaseAdvancedFilters;
  onChange: (next: ShowcaseAdvancedFilters) => void;
  /** The channel filter, shared with the bar's own source select. */
  source?: string;
  onSource: (next: string | undefined) => void;
}

export function AdvancedFilterSheet({
  open,
  onOpenChange,
  value,
  onChange,
  source,
  onSource
}: AdvancedFilterSheetProps) {
  const set = React.useCallback(
    (patch: Partial<ShowcaseAdvancedFilters>) => onChange({ ...value, ...patch }),
    [onChange, value]
  );

  /** The band whose bounds match what is applied, so it renders as selected. */
  const activeAgeBand = AGE_BANDS.find(
    (band) => band.min === value.min_year_built && band.max === value.max_year_built
  )?.key;

  const amenities: { key: keyof ShowcaseAdvancedFilters; label: string }[] = [
    { key: 'has_parking', label: 'پارکینگ' },
    { key: 'has_elevator', label: 'آسانسور' },
    { key: 'has_storage', label: 'انباری' },
    { key: 'has_balcony', label: 'بالکن' }
  ];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side='left' className='w-full sm:max-w-sm'>
        <SheetHeader>
          <SheetTitle className='flex items-center gap-2'>
            <Icons.adjustments className='size-4 text-gold-primary' aria-hidden />
            فیلترهای پیشرفته
          </SheetTitle>
          <SheetDescription>
            فیلترهای تخصصی شکار فایل؛ هر کدام روی فهرست همین صفحه اعمال می‌شود.
          </SheetDescription>
        </SheetHeader>

        <ScrollArea className='min-h-0 flex-1 px-4'>
          <div className='space-y-5 pb-2'>
            {/* -- تعداد خواب -- */}
            <Row label='تعداد خواب' hint='سوئیت را «۰ خواب» انتخاب کنید.'>
              <div className='flex flex-wrap gap-1.5'>
                {ROOM_OPTIONS.map((option) => {
                  const active =
                    value.min_rooms === option.min &&
                    (option.max === undefined
                      ? value.max_rooms === undefined
                      : value.max_rooms === option.max);
                  return (
                    <button
                      key={option.key}
                      type='button'
                      onClick={() =>
                        set(
                          active
                            ? { min_rooms: undefined, max_rooms: undefined }
                            : { min_rooms: option.min, max_rooms: option.max }
                        )
                      }
                      aria-pressed={active}
                      className={
                        active
                          ? 'border-gold-accent/60 bg-gold-accent/15 text-gold-primary h-8 rounded-full border px-3 text-[11px] font-semibold'
                          : 'border-border bg-muted/40 text-muted-foreground hover:text-foreground h-8 rounded-full border px-3 text-[11px] font-medium'
                      }
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </Row>

            {/* -- سن بنا -- */}
            <Row label='سن بنا' hint='ساختمان‌های فاقد سال ساخت در این فیلتر نمی‌آیند.'>
              <div className='flex flex-wrap gap-1.5'>
                {AGE_BANDS.map((band) => {
                  const active = activeAgeBand === band.key;
                  return (
                    <button
                      key={band.key}
                      type='button'
                      onClick={() =>
                        set({ min_year_built: band.min, max_year_built: band.max })
                      }
                      aria-pressed={active}
                      className={
                        active
                          ? 'border-gold-accent/60 bg-gold-accent/15 text-gold-primary h-8 rounded-full border px-3 text-[11px] font-semibold'
                          : 'border-border bg-muted/40 text-muted-foreground hover:text-foreground h-8 rounded-full border px-3 text-[11px] font-medium'
                      }
                    >
                      {band.label}
                    </button>
                  );
                })}
              </div>
            </Row>

            {/* -- طبقه -- */}
            <Row label='طبقه' hint='«آخرین طبقه» یعنی طبقهٔ واحد برابر با طبقات ساختمان.'>
              <div className='flex flex-wrap gap-1.5'>
                <button
                  type='button'
                  onClick={() => set({ min_floor: 0, max_floor: 0 })}
                  aria-pressed={value.min_floor === 0 && value.max_floor === 0}
                  className={
                    value.min_floor === 0 && value.max_floor === 0
                      ? 'border-gold-accent/60 bg-gold-accent/15 text-gold-primary h-8 rounded-full border px-3 text-[11px] font-semibold'
                      : 'border-border bg-muted/40 text-muted-foreground hover:text-foreground h-8 rounded-full border px-3 text-[11px] font-medium'
                  }
                >
                  همکف
                </button>
                <button
                  type='button'
                  onClick={() => set({ min_floor: 2, max_floor: undefined })}
                  aria-pressed={value.min_floor === 2 && value.max_floor === undefined}
                  className={
                    value.min_floor === 2 && value.max_floor === undefined
                      ? 'border-gold-accent/60 bg-gold-accent/15 text-gold-primary h-8 rounded-full border px-3 text-[11px] font-semibold'
                      : 'border-border bg-muted/40 text-muted-foreground hover:text-foreground h-8 rounded-full border px-3 text-[11px] font-medium'
                  }
                >
                  دوم به بالا
                </button>
                <button
                  type='button'
                  onClick={() =>
                    // A "last floor" filter needs the unit's floor to equal the
                    // building's, which is a row-level comparison the query
                    // params do not express; only the upper bound is offered
                    // until one does.
                    set({ min_floor: undefined, max_floor: undefined })
                  }
                  className='text-muted-foreground/60 border-border bg-muted/20 h-8 cursor-not-allowed rounded-full border px-3 text-[11px] font-medium'
                  title='به‌زودی'
                  aria-disabled
                >
                  آخرین طبقه
                </button>
              </div>
            </Row>

            {/* -- امکانات -- */}
            <Row
              label='امکانات'
              hint='پارکینگ در سامانه یک «دارد/ندارد» ثبت می‌شود؛ تفکیک اختصاصی و مزاحم فعلاً ممکن نیست.'
            >
              <div className='flex flex-wrap gap-1.5'>
                {amenities.map((item) => (
                  <AmenityChip
                    key={item.key}
                    label={item.label}
                    checked={Boolean(value[item.key])}
                    onToggle={() => set({ [item.key]: !value[item.key] })}
                  />
                ))}
              </div>
            </Row>

            {/* -- متراژ زمین -- */}
            <Row label='متراژ زمین / حیاط' hint='برای ویلا و باغ.'>
              <BoundPair
                fromValue={value.min_land_area}
                toValue={value.max_land_area}
                onFrom={(next) => set({ min_land_area: next })}
                onTo={(next) => set({ max_land_area: next })}
                fromPlaceholder='۰'
                toPlaceholder='∞'
                suffix='متر'
              />
            </Row>

            {/* -- قیمت هر متر -- */}
            <Row
              label='قیمت هر متر'
              hint='مجموع قیمت با قیمت متری فرق دارد؛ این بازه روی قیمت هر متر اعمال می‌شود.'
            >
              <BoundPair
                fromValue={value.min_price_per_meter}
                toValue={value.max_price_per_meter}
                onFrom={(next) => set({ min_price_per_meter: next })}
                onTo={(next) => set({ max_price_per_meter: next })}
                fromPlaceholder='۰'
                toPlaceholder='∞'
                suffix='تومان'
              />
            </Row>

            {/* -- رادار -- */}
            <Row
              label='رادار شکار قیمت'
              hint='آگهی‌هایی که هر متر آن‌ها حداقل به این مقدار از میانگین محلهٔ خود ارزان‌تر است. فایل‌های بدون برچسب قیمت در این فیلتر نمی‌آیند.'
            >
              <div className='flex flex-wrap gap-1.5'>
                {[5, 10, 15, 20].map((pct) => {
                  const active = value.below_market_pct === pct;
                  return (
                    <button
                      key={pct}
                      type='button'
                      onClick={() => set({ below_market_pct: active ? undefined : pct })}
                      aria-pressed={active}
                      className={
                        active
                          ? 'border-gold-accent/60 bg-gold-accent/15 text-gold-primary h-8 rounded-full border px-3 text-[11px] font-semibold tabular-nums'
                          : 'border-border bg-muted/40 text-muted-foreground hover:text-foreground h-8 rounded-full border px-3 text-[11px] font-medium tabular-nums'
                      }
                    >
                      {pct}٪ زیر عرف
                    </button>
                  );
                })}
              </div>
            </Row>

            {/* -- منبع و ثبت‌کننده -- */}
            <Row label='منبع آگهی' hint='ثبت مستقیم مالک از خزندهٔ پورتال قابل اعتمادتر است.'>
              <div className='space-y-2'>
                {SOURCE_GROUPS.map((group) => (
                  <div key={group.label} className='space-y-1'>
                    <p className='text-[11px] font-semibold'>{group.label}</p>
                    <div className='flex flex-wrap gap-1.5'>
                      {group.sources.map((sourceKey) => {
                        const active = source === sourceKey;
                        return (
                          <button
                            key={sourceKey}
                            type='button'
                            onClick={() => onSource(active ? undefined : sourceKey)}
                            aria-pressed={active}
                            className={
                              active
                                ? 'border-gold-accent/60 bg-gold-accent/15 text-gold-primary h-7 rounded-full border px-2.5 text-[11px] font-semibold'
                                : 'border-border bg-muted/40 text-muted-foreground hover:text-foreground h-7 rounded-full border px-2.5 text-[11px] font-medium'
                            }
                          >
                            {SOURCE_LABELS[sourceKey]}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </Row>

            <Row
              label='ثبت‌کننده'
              hint='«شخص حقیقی» یعنی مالک خودش فایل را ثبت کرده.'
            >
              <NativeSelect
                className='h-8 text-xs'
                value={value.submitter_type ?? ''}
                onChange={(event) =>
                  set({
                    submitter_type: event.target.value
                      ? (event.target.value as SubmitterType)
                      : undefined
                  })
                }
              >
                <option value=''>همه</option>
                <option value={SUBMITTER_TYPES[0]}>{SUBMITTER_LABELS[SUBMITTER_TYPES[0]]}</option>
                <option value={SUBMITTER_TYPES[1]}>{SUBMITTER_LABELS[SUBMITTER_TYPES[1]]}</option>
              </NativeSelect>
            </Row>

            {/* -- زمان انتشار -- */}
            <Row label='زمان انتشار' hint='تازه‌ترین فایل، اولین فرصت مذاکره است.'>
              <div className='flex flex-wrap gap-1.5'>
                {PUBLISHED_WINDOWS.map((window) => {
                  const active = value.published_within_hours === window.hours;
                  return (
                    <button
                      key={window.value}
                      type='button'
                      onClick={() =>
                        set({ published_within_hours: active ? undefined : window.hours })
                      }
                      aria-pressed={active}
                      className={
                        active
                          ? 'border-gold-accent/60 bg-gold-accent/15 text-gold-primary h-8 rounded-full border px-3 text-[11px] font-semibold'
                          : 'border-border bg-muted/40 text-muted-foreground hover:text-foreground h-8 rounded-full border px-3 text-[11px] font-medium'
                      }
                    >
                      {window.label}
                    </button>
                  );
                })}
              </div>
            </Row>
          </div>
        </ScrollArea>

        <SheetFooter>
          <div className='flex w-full items-center gap-2'>
            {/*
              Clears the shared source too. Leaving it set would keep a filter
              applied that the advisor has just told the panel to forget — and
              the bar's select would still show it, which is how a "cleared"
              filter stays quietly in force.
            */}
            <Button
              type='button'
              variant='ghost'
              size='sm'
              className='flex-1'
              onClick={() => {
                onChange({});
                onSource(undefined);
              }}
            >
              پاک کردن همه
            </Button>
            <Button type='button' size='sm' className='flex-1' onClick={() => onOpenChange(false)}>
              نمایش نتایج
            </Button>
          </div>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
