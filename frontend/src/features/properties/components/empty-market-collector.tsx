'use client';

import * as React from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ensureMarketInventory } from '../api/client';

/** A POST, never a side effect of the public inventory GET. Server rechecks
 * unfiltered inventory, serializes requests and enforces its retry cooldown. */
export function EmptyMarketCollector({ cities, empty }: { cities: string[]; empty: boolean }) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ['market-demand', [...new Set(cities)].sort()],
    queryFn: () => ensureMarketInventory(cities),
    enabled: empty && cities.length > 0,
    retry: false,
    staleTime: 600_000,
    refetchOnWindowFocus: false,
    refetchInterval: (q) => q.state.data?.items.some((item) => item.status === 'collecting' || item.status === 'partial') ? 5000 : false
  });
  React.useEffect(() => {
    if (!query.data) return;
    void client.invalidateQueries({ queryKey: ['properties'] });
    void client.invalidateQueries({ queryKey: ['bargains'] });
    void client.invalidateQueries({ queryKey: ['market'] });
  }, [client, query.data, query.dataUpdatedAt]);
  if (!empty || !cities.length) return null;
  let message = 'در حال بررسی موجودی و ثبت درخواست جمع‌آوری آگهی…';
  if (query.isError) message = `درخواست جمع‌آوری ثبت نشد: ${query.error.message}`;
  else if (query.data) {
    const items = query.data.items;
    const states = items.map((item) => item.status);
    if (states.includes('collecting') || states.includes('partial')) {
      const collecting = items.flatMap((item) => Object.entries(item.sources ?? {}).filter(([, state]) => state === 'collecting').map(([source]) => source));
      message = `در حال جمع‌آوری از ${collecting.join('، ') || 'منابع فعال'}؛ نتایج به‌صورت خودکار به‌روز می‌شوند.`;
    }
    else if (states.includes('failed')) {
      const failed = items.flatMap((item) => Object.entries(item.sources ?? {}).filter(([, state]) => state === 'failed').map(([source]) => source));
      message = `جمع‌آوری ناموفق از ${failed.join('، ') || 'منبع'}`;
    }
    else if (states.includes('disabled')) message = 'خزنده در این سامانه غیرفعال است.';
    else if (states.includes('unsupported')) message = 'برای این شهر در منابع فعال، نگاشت معتبر خزش موجود نیست.';
    else if (states.includes('available')) message = 'در این شهر آگهی وجود دارد؛ فیلترهای دیگر را بررسی کنید.';
    else message = 'جمع‌آوری پایان یافت، اما هنوز آگهی جدیدی دریافت نشد.';
  }
  return <p role='status' className='text-muted-foreground text-sm'>{message}</p>;
}