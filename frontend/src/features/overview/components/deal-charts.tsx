'use client';

import { useEffect, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { authHeaders } from '@/lib/auth/session';
import { apiBaseUrl } from '@/lib/api-base-url';

export interface DealSummaryItem {
  deal_type: string;
  count: number;
  value: number;
}

export interface DealSummary {
  deals: DealSummaryItem[];
}

const DEAL_TYPE_LABELS: Record<string, string> = {
  SALE: 'خرید',
  RENT: 'اجاره',
};

const METRICS = [
  { key: 'count', label: 'تعداد آگهی‌ها' },
  { key: 'value', label: 'ارزش کل' },
] as const;

type MetricKey = (typeof METRICS)[number]['key'];

export function DealCharts() {
  const [summary, setSummary] = useState<DealSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const headers = await authHeaders();
        const res = await fetch(`${apiBaseUrl()}/properties/deal-summary`, {
          headers,
        });

        if (!res.ok) {
          let detail = `سرویس داده در دسترس نیست (کد ${res.status})`;
          try {
            const body = (await res.json()) as {
              detail?: { error?: string; message?: string };
            };
            detail = body.detail?.error || body.detail?.message || detail;
          } catch {
            // non-JSON body
          }
          throw new Error(detail);
        }

        const data = (await res.json()) as DealSummary;
        if (!cancelled) setSummary(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'خطای نا-known در برقراری ارتباط.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const sale = summary?.deals.find((d) => d.deal_type === 'SALE') ?? null;
  const rent = summary?.deals.find((d) => d.deal_type === 'RENT') ?? null;

  const buildData = (count: boolean): Array<{ name: string; value: number }> => {
    const valueOf = (item: DealSummaryItem | null): number =>
      item ? (count ? item.count : item.value ?? 0) : 0;
    return [
      { name: DEAL_TYPE_LABELS.SALE ?? 'خرید', value: valueOf(sale) },
      { name: DEAL_TYPE_LABELS.RENT ?? 'اجاره', value: valueOf(rent) },
    ];
  };

  const formatValue = (metric: MetricKey, value: number): string => {
    const formatted = value.toLocaleString('en-US');
    return metric === 'value' ? `${formatted} تومان` : `${formatted} آگهی`;
  };

  if (loading) {
    return (
      <div className='grid grid-cols-1 gap-4 md:grid-cols-2'>
        {METRICS.map((m, index) => (
          <div
            key={m.key}
            className='rounded-xl border border-border/60 bg-card/40 p-4'
          >
            <div className='h-4 w-32 rounded bg-muted' />
            <div className='mt-4 flex h-[260px] items-end justify-around gap-2'>
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className='rounded-t bg-muted/60'
                  style={{ height: `${20 + Math.random() * 120}%` }}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className='rounded-xl border border-destructive/30 bg-destructive/10 p-4'>
        <p className='text-sm text-destructive'>{error}</p>
      </div>
    );
  }

  return (
    <div className='grid grid-cols-1 gap-4 md:grid-cols-2'>
      {METRICS.map((metric) => {
        const data = buildData(metric.key === 'count');
        const total = data.reduce((sum, item) => sum + item.value, 0);
        return (
          <div
            key={metric.key}
            className='rounded-xl border border-border/60 bg-card/40 p-4 shadow-sm'
          >
            <div className='flex items-center justify-between'>
              <h3 className='text-sm font-semibold'>{metric.label}</h3>
              <span className='text-xs text-muted-foreground'>
                مجموع: {formatValue(metric.key, total)}
              </span>
            </div>
            <ResponsiveContainer aspect={1.5} className='mt-4'>
              <BarChart data={data}>
                <XAxis
                  dataKey='name'
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 13, fill: 'hsl(var(--muted-foreground))' }}
                />
                <YAxis
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 12, fill: 'hsl(var(--muted-foreground))' }}
                />
                <Tooltip
                  cursor={{ fill: 'hsl(var(--muted)/40)' }}
                  content={<CustomTooltip metric={metric.key} />}
                />
                <Bar dataKey='value' radius={[4, 4, 0, 0]}>
                  {data.map((_, i) => (
                    <Cell
                      key={i}
                      fill={i === 0 ? 'hsl(var(--blue-500))' : 'hsl(var(--green-500))'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div className='mt-2 flex justify-between text-xs text-muted-foreground'>
              <span>{DEAL_TYPE_LABELS.SALE ?? 'خرید'}</span>
              <span>{DEAL_TYPE_LABELS.RENT ?? 'اجاره'}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function CustomTooltip({
  metric,
  active,
  payload,
}: {
  metric: MetricKey;
  active?: boolean;
  payload?: Array<{ value: number }>;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const value = payload[0].value ?? 0;
  return (
    <div className='rounded-lg border border-border/60 bg-background/95 p-2 shadow-sm'>
      <p className='text-xs text-muted-foreground'>
        {metric === 'count' ? 'تعداد آگهی‌ها' : 'ارزش کل'}
      </p>
      <p className='text-sm font-semibold'>
        <span className='mr-1'>مقدار:</span>
        <span className='mr-1'>
          {metric === 'value' ? 'تومان' : 'آگهی'}:
        </span>
        <span className='font-medium'>{value.toLocaleString('en-US')}</span>
      </p>
    </div>
  );
}
