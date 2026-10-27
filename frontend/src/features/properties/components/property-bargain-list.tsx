"use client";

import { Icons } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty';
import { useState } from 'react';
import { ListingCard } from './listing-card';
import { useBargains } from '../hooks';
import { useLocationFilter } from '../hooks/use-location-filter';

/**
 * Bargain radar feed.
 *
 * The engine only emits a BARGAIN verdict when the district had enough
 * comparables, so an empty list usually means "no data yet" rather than
 * "no opportunities" -- the copy says so instead of showing a dead end.
 */
export function PropertyBargainList() {
  const [neighborhood, setNeighborhood] = useState("");
  const [appliedNeighborhood, setAppliedNeighborhood] = useState("");
  // پل City Gate: رادار شکار فقط آگهی‌های شهر فعال را نشان می‌دهد.
  const { cities } = useLocationFilter();

  const { data, isPending, isError, error, refetch, isFetching } = useBargains(
    {
      ...(appliedNeighborhood ? { neighborhood: appliedNeighborhood } : {}),
      ...(cities.length ? { cities } : {}),
      limit: 60
    }
  );

  function applyFilter(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAppliedNeighborhood(neighborhood.trim());
  }

  if (isPending) {
    return (
      <div className='flex items-center justify-center py-16'>
        <Icons.spinner className='text-muted-foreground size-6 animate-spin' />
        <span className='text-muted-foreground me-3 text-sm'>در حال دریافت رادار شکار...</span>
      </div>
    );
  }

  if (isError) {
    return (
      <Empty className='border'>
        <EmptyHeader>
          <Icons.warning className='text-destructive size-6' />
          <EmptyTitle>دریافت رادار ناموفق بود</EmptyTitle>
          <EmptyDescription>
            {(error as Error)?.message ?? "ارتباط با نود آفیس برقرار نشد."}
          </EmptyDescription>
        </EmptyHeader>
        <div className='flex justify-center'>
          <Button variant='outline' onClick={() => void refetch()}>
            تلاش دوباره
          </Button>
        </div>
      </Empty>
    );
  }

  const items = data?.items ?? [];

  return (
    <div className='flex flex-col gap-4'>
      <form onSubmit={applyFilter} className='flex items-end gap-2'>
        <div className='flex flex-col gap-1'>
          <label htmlFor='neighborhood' className='text-muted-foreground text-xs'>
            محله
          </label>
          <Input
            id='neighborhood'
            value={neighborhood}
            onChange={(event) => setNeighborhood(event.target.value)}
            placeholder='مثلاً جردن'
            className='w-56'
          />
        </div>
        <Button type='submit' variant='outline'>
          اعمال فیلتر
        </Button>
        <Button type='button' variant='ghost' onClick={() => void refetch()} disabled={isFetching}>
          {isFetching ? "در حال به‌روزرسانی..." : "به‌روزرسانی"}
        </Button>
      </form>

      {items.length === 0 ? (
        <Empty className='border'>
          <EmptyHeader>
            <EmptyTitle>موردی زیر قیمت بازار پیدا نشد</EmptyTitle>
            <EmptyDescription>
              ارزش‌گذاری خودکار فقط زمانی حکم صادر می‌کند که حداقل نمونه کافی در همان محله موجود باشد.
              با ثبت فایل‌های بیشتر، رادار دقیق‌تر می‌شود.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <>
          <p className='text-muted-foreground text-xs'>
            {data?.count ?? items.length} فایل زیر قیمت بازار
          </p>
          <div className='grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3'>
            {items.map((property) => (
              <ListingCard key={property.id} property={property} emphasis />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
