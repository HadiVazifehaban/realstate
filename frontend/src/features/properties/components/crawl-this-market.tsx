'use client';

import * as React from 'react';
import { toast } from 'sonner';
import { Icons } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { toPersianDigits } from '@/lib/utils';
import { triggerScrape } from '../api/client';

/**
 * Send the market the advisor is currently looking at to the scrapers.
 *
 * The filter already says which cities this desk is working, so the node's next
 * sweep should cover exactly that. Before this, the crawl followed whatever
 * ``SCRAPER_CITIES`` was set to at deploy time — an advisor who filtered to
 * Karaj still got a Tehran crawl, and the market they asked for stayed stale
 * until someone edited the node's environment.
 *
 * One press queues one job per city, which the node answers with the first
 * job; the toast counts the market rather than pretending it queued one
 * sweep for all of them.
 */
export function CrawlThisMarket({ cities }: { cities: string[] }) {
  const [pending, setPending] = React.useState(false);

  const onCrawl = React.useCallback(async () => {
    if (cities.length === 0) return;
    setPending(true);
    try {
      await triggerScrape({ cities });
      toast.success(
        `جست‌وجوی ${toPersianDigits(cities.length.toLocaleString('en-US'))} شهر در نوبت خزنده قرار گرفت.`
      );
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'ثبت درخواست خزنده ناموفق بود.';
      toast.error(message);
    } finally {
      setPending(false);
    }
  }, [cities]);

  if (cities.length === 0) return null;

  return (
    <Button
      variant='outline'
      size='sm'
      className='h-8 gap-1.5'
      disabled={pending}
      onClick={() => void onCrawl()}
      title='آگهی‌های این شهرها همین حالا خزیده شوند'
    >
      {pending ? (
        <Icons.spinner className='size-3.5 animate-spin' aria-hidden />
      ) : (
        <Icons.refresh className='size-3.5' aria-hidden />
      )}
      جست‌وجوی این بازار
    </Button>
  );
}

export default CrawlThisMarket;
