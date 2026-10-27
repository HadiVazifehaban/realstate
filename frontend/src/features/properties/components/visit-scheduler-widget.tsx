"use client";

import * as React from 'react';
import { Icons } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn, toPersianDigits } from '@/lib/utils';
import { useBookVisitSlot, useVisitAvailability } from '../hooks';
import { VISIT_SLOT_KIND_LABELS } from '../types';
import type { VisitAvailabilityItem, VisitBookingRequest, VisitSlotKind } from '../types';
import {
  JALALI_MONTH_NAMES,
  JALALI_WEEKDAY_NAMES,
  formatJalaliLong,
  isoToJalali,
  jalaliMonthLength,
  jalaliMonthStartOffset,
  shortTime,
  toGregorian,
  todayIsoLocal,
  todayJalali
} from '../utils/jalali';

/**
 * Visit scheduler: a Jalali month grid over the desk's free viewing windows.
 *
 * The listing itself carries no schedule -- every window lives on
 * `property_visit_booking` -- so this widget is the only place on the page that
 * talks about time. It asks the node for the *visible month* only: a wider
 * range would ship dozens of 09:00 holes the user never scrolls to.
 *
 * Calendar shape: Saturday-first, like every Iranian wall calendar, with the
 * 1st of the month pushed right by however many empty cells the month start
 * needs. Past days and Fridays are rendered dead: the node skips Friday itself,
 * so offering it here would manufacture a request the desk has to refuse.
 *
 * A click always *requests*, never confirms -- the row lands as REQUESTED and
 * the desk confirms it on the CRM board. A 409 (`slot_taken`) means someone
 * raced us for the hour, so the hour disappears on the refetch and the user
 * picks another; that is normal traffic, not an error.
 */

interface VisitSchedulerWidgetProps {
  propertyId: string;
  className?: string;
  compact?: boolean;
}

/** Pad to the `YYYY-MM-DD` the wire expects. */
function isoOf(gy: number, gm: number, gd: number): string {
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${gy}-${pad(gm)}-${pad(gd)}`;
}

/** Gregorian ISO date of the Nth day of a Jalali month. */
function dayIsoOf(jy: number, jm: number, jd: number): string {
  const { year, month, day } = toGregorian(jy, jm, jd);
  return isoOf(year, month, day);
}

export function VisitSchedulerWidget({ propertyId, className, compact = false }: VisitSchedulerWidgetProps) {
  const initial = todayJalali();
  const [year, setYear] = React.useState(initial.year);
  const [month, setMonth] = React.useState(initial.month);
  const [selected, setSelected] = React.useState<string | null>(null);
  const [expanded, setExpanded] = React.useState(!compact);
  const [guests, setGuests] = React.useState('');
  const [notes, setNotes] = React.useState('');
  const [kind, setKind] = React.useState<VisitSlotKind>('OFFICE_HOUSE');

  const monthLength = jalaliMonthLength(year, month);
  const firstIso = dayIsoOf(year, month, 1);
  const lastIso = dayIsoOf(year, month, monthLength);
  const todayIso = todayIsoLocal();

  const { data, isPending, isError } = useVisitAvailability(propertyId, {
    dateFrom: firstIso,
    dateTo: lastIso
  });
  const book = useBookVisitSlot(propertyId);

  // Group the feed by day: one lookup marks a day "has free windows" in the
  // grid, and the detail panel lists the free hours without rescanning.
  const byDay = React.useMemo(() => {
    const map = new Map<string, VisitAvailabilityItem[]>();
    for (const item of data?.items ?? []) {
      const bucket = map.get(item.slot_date);
      if (bucket) bucket.push(item);
      else map.set(item.slot_date, [item]);
    }
    return map;
  }, [data]);

  const step = (delta: number) => {
    setSelected(null);
    const index = month - 1 + delta;
    setYear(year + Math.floor(index / 12));
    setMonth((((index % 12) + 12) % 12) + 1);
  };

  const offset = jalaliMonthStartOffset(year, month);
  const freeCount = (iso: string) =>
    (byDay.get(iso) ?? []).filter((item) => item.available).length;

  const selectedSlots = selected ? byDay.get(selected) ?? [] : [];
  const freeSlots = selectedSlots.filter((item) => item.available);

  const submit = (slot: VisitAvailabilityItem) => {
    const payload: VisitBookingRequest = {
      slot_date: slot.slot_date,
      start_time: shortTime(slot.start_time),
      end_time: slot.end_time ? shortTime(slot.end_time) : null,
      kind,
      guests: guests ? Number(guests) : null,
      notes: notes.trim() || null
    };
    book.mutate(payload, { onSuccess: () => setSelected(null) });
  };

  return (
    <section className={cn('showcase-panel min-w-0 overflow-hidden p-4 sm:p-5', className, compact && 'property-detail-scheduler', compact && !expanded && 'property-detail-scheduler-collapsed')}>
      <div className='mb-4 flex min-w-0 flex-wrap items-center justify-between gap-2'>
        <h2 className='showcase-section-title text-sm'>رزرو بازدید</h2>
        {compact && !expanded ? (
          <Button type='button' size='sm' variant='outline' className='h-8 gap-1.5 text-xs' onClick={() => setExpanded(true)}>
            <Icons.calendar className='size-3.5' />
            انتخاب زمان بازدید
          </Button>
        ) : <div className='flex items-center gap-1'>
          <button
            type='button'
            className='showcase-circle-button size-8'
            aria-label='ماه قبل'
            onClick={() => step(-1)}
          >
            <Icons.chevronRight className='size-4' />
          </button>
          <span className='min-w-24 text-center text-sm font-semibold tabular-nums'>
            {`${JALALI_MONTH_NAMES[month - 1]} ${toPersianDigits(String(year))}`}
          </span>
          <button
            type='button'
            className='showcase-circle-button size-8'
            aria-label='ماه بعد'
            onClick={() => step(1)}
          >
            <Icons.chevronLeft className='size-4' />
          </button>
          {compact && <Button type='button' size='sm' variant='ghost' className='ms-1 h-8 px-2 text-xs' onClick={() => setExpanded(false)}>بستن</Button>}
        </div>}
      </div>

      {(!compact || expanded) && <div className={cn(compact && 'property-detail-scheduler-body')}>
      {isError ? (
        <p className='text-muted-foreground py-6 text-center text-xs'>
          تقویم بازدید در دسترس نیست.
        </p>
      ) : isPending ? (
        <Skeleton className='h-56 w-full' />
      ) : (
        <>
          <div className='mb-1 grid grid-cols-7 gap-1 text-center text-xs text-[var(--gold-accent)]'>
            {JALALI_WEEKDAY_NAMES.map((name) => (
              <span key={name} className='py-1'>
                {name}
              </span>
            ))}
          </div>
          <div className='grid grid-cols-7 gap-1' role='grid' aria-label='تقویم بازدید'>
            {Array.from({ length: offset }, (_, index) => (
              <span key={`pad-${index}`} aria-hidden />
            ))}
            {Array.from({ length: monthLength }, (_, index) => {
              const day = index + 1;
              const iso = dayIsoOf(year, month, day);
              const free = freeCount(iso);
              const dead = iso < todayIso || (offset + index) % 7 === 6;
              return (
                <button
                  key={iso}
                  type='button'
                  disabled={dead || free === 0}
                  aria-current={iso === selected}
                  onClick={() => setSelected(iso === selected ? null : iso)}
                  className={cn(
                    'relative aspect-square rounded-lg text-sm tabular-nums transition-colors',
                    iso === selected && 'bg-[var(--gold-accent)] text-showcase font-semibold',
                    iso !== selected && free > 0 && 'text-showcase ring-1 ring-[var(--gold-accent)]/40 hover:bg-showcase-surface-deep',
                    dead && 'text-showcase-dim/40',
                    !dead && free === 0 && 'text-showcase-dim'
                  )}
                >
                  {toPersianDigits(String(day))}
                  {!dead && free > 0 && iso !== selected && (
                    <span className='absolute bottom-1 start-1/2 size-1 -translate-x-1/2 rounded-full bg-[var(--gold-accent)]' />
                  )}
                </button>
              );
            })}
          </div>

          {selected && (
            <div className='mt-4 border-t border-white/10 pt-4'>
              <p className='mb-3 text-sm font-semibold'>
                {formatJalaliLong(isoToJalali(selected))}
              </p>
              {freeSlots.length === 0 ? (
                <p className='text-muted-foreground text-xs'>
                  ساعتی آزاد برای این روز نیست؛ روز دیگری انتخاب کنید.
                </p>
              ) : (
                <div className='flex flex-wrap gap-2'>
                  {freeSlots.map((slot) => (
                    <button
                      key={slot.start_time}
                      type='button'
                      disabled={book.isPending}
                      onClick={() => submit(slot)}
                      className='rounded-lg border border-[var(--gold-accent)]/40 px-3 py-1.5 text-sm tabular-nums transition-colors hover:bg-[var(--gold-accent)]/15 disabled:opacity-50'
                    >
                      {toPersianDigits(shortTime(slot.start_time))}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className='mt-4 flex flex-col gap-2 text-xs'>
            <label className='flex items-center gap-2'>
              <span className='text-showcase-dim w-16 shrink-0'>نوع بازدید</span>
              <select
                value={kind}
                onChange={(event) => setKind(event.target.value as VisitSlotKind)}
                className='flex-1 rounded-lg border border-white/10 bg-transparent px-2 py-1.5'
              >
                {(Object.keys(VISIT_SLOT_KIND_LABELS) as VisitSlotKind[]).map((value) => (
                  <option key={value} value={value} className='text-black'>
                    {VISIT_SLOT_KIND_LABELS[value]}
                  </option>
                ))}
              </select>
            </label>
            <label className='flex items-center gap-2'>
              <span className='text-showcase-dim w-16 shrink-0'>تعداد نفرات</span>
              <input
                inputMode='numeric'
                value={guests}
                onChange={(event) => setGuests(event.target.value.replace(/[^\d]/g, ''))}
                placeholder='۱'
                className='flex-1 rounded-lg border border-white/10 bg-transparent px-2 py-1.5 tabular-nums'
              />
            </label>
            <label className='flex items-start gap-2'>
              <span className='text-showcase-dim w-16 shrink-0'>توضیح</span>
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                rows={2}
                placeholder='مثلاً: ترجیحاً بعدازظهر'
                className='flex-1 resize-none rounded-lg border border-white/10 bg-transparent px-2 py-1.5'
              />
            </label>
          </div>

          <p className='text-showcase-dim mt-3 text-xs leading-relaxed'>
            درخواست شما ثبت می‌شود و دفتر برای تأیید نهایی با شما تماس می‌گیرد.
          </p>

          <Button
            type='button'
            className='mt-3 w-full'
            disabled={!selected || freeSlots.length === 0 || book.isPending}
            onClick={() => {
              if (freeSlots[0]) submit(freeSlots[0]);
            }}
          >
            {book.isPending ? 'در حال ثبت…' : 'ثبت درخواست بازدید'}
          </Button>
        </>
      )}
      </div>}
    </section>
  );
}
