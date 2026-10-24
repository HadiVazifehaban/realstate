'use client';

import * as React from 'react';

import { Icons } from '@/components/icons';
import { cn, formatToman } from '@/lib/utils';

import { useBoardStats } from '../hooks';
import {
  KANBAN_COLUMNS,
  LEAD_STAGE_LABELS,
  STAGE_ACCENTS,
  type Actor,
  type BoardStats,
  type LeadStage
} from '../types';

const fa = new Intl.NumberFormat('fa-IR');

/**
 * Desk totals above the board.
 *
 * The numbers are aggregated server-side over *every* lead, not over the cards
 * currently rendered, so the strip stays correct while the broker filters the
 * board — a header that counts the visible cards would make "فقط شکارها"
 * look like the whole pipeline.
 *
 * Failures are reported inline rather than with the board's full-width error
 * state: the columns below are still usable without the totals, and a header
 * that hides the desk behind a warning costs more than it explains.
 */
export function BoardStatsStrip({ actor }: { actor?: Actor }) {
  const { data, isPending, isError } = useBoardStats(actor);

  if (isPending) {
    return (
      <div className='mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-6'>
        {KANBAN_COLUMNS.map((stage) => (
          <div key={stage} className='bg-card/60 rounded-xl border p-3'>
            <div className='bg-muted h-3 w-2/3 rounded' />
            <div className='bg-muted mt-2 h-4 w-1/3 rounded' />
          </div>
        ))}
      </div>
    );
  }

  if (isError || !data) {
    return (
      <p className='text-muted-foreground mb-4 flex items-center gap-2 rounded-xl border border-dashed px-4 py-3 text-xs'>
        <Icons.warning className='size-4' />
        آمار تخته در دسترس نیست؛ ستون‌ها با همان داده‌های قبلی کار می‌کنند.
      </p>
    );
  }

  return (
    <div className='mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-6'>
      {KANBAN_COLUMNS.map((stage) => {
        const stat = data.columns.find((column) => column.stage === stage);
        return (
          <ColumnChip key={stage} stage={stage} count={stat?.count ?? 0} value={stat?.total_value ?? 0} />
        );
      })}
      <DeskTotals stats={data} />
    </div>
  );
}

/** One column's depth and value, tinted with the same accent as its header. */
function ColumnChip({ stage, count, value }: { stage: LeadStage; count: number; value: number }) {
  const accent = STAGE_ACCENTS[stage];

  return (
    <div
      style={
        {
          '--chip-accent': accent.stripe,
          borderTopColor: 'var(--chip-accent)'
        } as React.CSSProperties
      }
      className='bg-card/60 rounded-xl border border-t-2 px-3 py-2'
    >
      <div className='flex items-baseline justify-between gap-2'>
        <span className='text-muted-foreground truncate text-xs'>
          {LEAD_STAGE_LABELS[stage]}
        </span>
        <span className='text-sm font-semibold tabular-nums'>
          {fa.format(count)}
        </span>
      </div>
      <span className='text-muted-foreground block truncate text-[11px] tabular-nums'>
        {formatToman(value)}
      </span>
    </div>
  );
}

/**
 * The four numbers a broker checks before reading a single card.
 *
 * `conversion_pct` is won / (won + lost) — files still being worked are left
 * out of the denominator on purpose, because a desk with forty live leads and
 * two closed ones would otherwise read as a 5% win rate.
 */
function DeskTotals({ stats }: { stats: BoardStats }) {
  return (
    <div className='bg-card/60 rounded-xl border px-3 py-2 sm:col-span-2 lg:col-span-1'>
      <dl className='flex h-full flex-col justify-between gap-1.5'>
        <Total label='کل لیدهای تخته' value={fa.format(stats.total)} />
        <Total
          label='ارزش خط لوله'
          value={formatToman(stats.open_value)}
          hint='فایل‌های در جریان'
        />
        <Total
          label='نرخ برد'
          value={`${fa.format(stats.conversion_pct)}٪`}
          hint={`بسته‌شده: ${formatToman(stats.closed_value)}`}
        />
        <div className='flex items-center gap-2'>
          <span className='text-muted-foreground flex items-center gap-1 text-[11px]'>
            <Icons.trendingDown className='size-3.5' />
            شکار: {fa.format(stats.bargains)}
          </span>
          <span className='text-muted-foreground flex items-center gap-1 text-[11px]'>
            <Icons.archive className='size-3.5' />
            بایگانی: {fa.format(stats.lost)}
          </span>
        </div>
      </dl>
    </div>
  );
}

function Total({
  label,
  value,
  hint,
  className
}: {
  label: string;
  value: string;
  hint?: string;
  className?: string;
}) {
  return (
    <div className={cn('flex items-baseline justify-between gap-2', className)}>
      <dt className='text-muted-foreground text-[11px]'>{label}</dt>
      <dd className='flex items-baseline gap-1.5'>
        {hint && <span className='text-muted-foreground text-[10px]'>{hint}</span>}
        <span className='text-sm font-semibold tabular-nums'>{value}</span>
      </dd>
    </div>
  );
}
