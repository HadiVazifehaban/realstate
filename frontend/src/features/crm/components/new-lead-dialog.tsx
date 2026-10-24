'use client';

import * as React from 'react';
import { Icons } from '@/components/icons';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { useProperties } from '@/features/properties/hooks';
import { useDebounce } from '@/hooks/use-debounce';
import { formatToman } from '@/lib/utils';
import { leadSourceBadge } from '../types';
import type { Actor } from '../types';
import { useCreateLead, useLeads } from '../hooks';

/**
 * "Add lead" for the broker desk.
 *
 * The board's cards are leads, and a lead is a *view of an existing listing* —
 * it carries no title, price or specs of its own. So this dialog picks a
 * listing rather than asking the broker to type a new one: creating a lead for
 * a property that does not exist would put a card on the desk with nothing
 * behind it. To register a brand-new unit, use the property wizard.
 *
 * It lives in its own module because two screens need it: the CRM board, where
 * the desk starts, and the office listing feed, where the advisor is already
 * looking at the file worth working. Importing it from the board's page component
 * would have dragged the whole board — drag-and-drop, timeline drawer, stats —
 * into the feed's route bundle for one dialog.
 */
export function NewLeadDialog({ actor }: { actor?: Actor }) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState('');

  // The node holds thousands of listings, so the search has to run server-side:
  // filtering a client-side page would make every listing older than that page
  // unfindable. Debounced because each keystroke would otherwise hit Postgres.
  const debouncedQuery = useDebounce(query.trim(), 300);

  const { data, isPending } = useProperties({
    // The node accumulates well over a thousand scraped listings a day, so the
    // picker pulls the whole feed in one pass rather than paging: the broker
    // scrolls a list, they do not paginate a shortlist. Kept at 2500 to sit
    // under the endpoint's cap with headroom for a busy weekend.
    limit: 2500,
    ...(debouncedQuery ? { q: debouncedQuery } : {})
  });
  const createLead = useCreateLead(actor);

  // Hide listings that already have a card. `POST /crm/leads` is idempotent and
  // would return the existing card, but offering them here just invites the
  // broker to click one and wonder why the board did not change.
  const { data: leadData } = useLeads({ limit: 500 }, actor);
  const takenPropertyIds = React.useMemo(
    () => new Set((leadData?.items ?? []).map((lead) => lead.property_id)),
    [leadData]
  );

  const total = data?.count ?? 0;
  const items = (data?.items ?? []).filter((item) => !takenPropertyIds.has(item.id));

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    // Reset on close so reopening always starts from the newest listings
    // rather than whatever search the broker left behind.
    if (!next) setQuery('');
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={<Button size='sm' />}>
        <Icons.add className='size-4' />
        افزودن لید
      </DialogTrigger>
      <DialogContent className='sm:max-w-lg'>
        <DialogHeader>
          <DialogTitle>افزودن لید به تخته</DialogTitle>
          <DialogDescription>
            جدیدترین آگهی‌های ثبت‌شده را انتخاب کنید. جست‌وجو عنوان یا محله را
            دربر می‌گیرد.
          </DialogDescription>
        </DialogHeader>

        <div className='relative'>
          <Icons.search className='text-muted-foreground absolute top-1/2 right-3 size-4 -translate-y-1/2' />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder='جست‌وجو در عنوان یا محله…'
            className='pr-9'
            aria-label='جست‌وجوی آگهی'
          />
        </div>

        <div className='max-h-[26rem] space-y-1.5 overflow-y-auto'>
          {isPending && (
            <div className='space-y-2'>
              <Skeleton className='h-12 w-full' />
              <Skeleton className='h-12 w-full' />
              <Skeleton className='h-12 w-full' />
            </div>
          )}

          {!isPending && items.length === 0 && (
            <p className='text-muted-foreground py-6 text-center text-sm'>
              {debouncedQuery
                ? 'آگهی‌ای با این عبارت پیدا نشد.'
                : 'آگهی تازه‌ای برای افزودن نیست. ابتدا از بخش «ثبت ملک» یک آگهی ثبت کنید.'}
            </p>
          )}

          {!isPending &&
            items.map((item) => (
              <button
                key={item.id}
                type='button'
                disabled={createLead.isPending}
                onClick={() =>
                  createLead.mutate(item.id, { onSuccess: () => setOpen(false) })
                }
                className='hover:bg-accent flex w-full items-center justify-between gap-3 rounded-lg border p-2.5 text-right disabled:opacity-50'
              >
                <div className='min-w-0'>
                  <span className='line-clamp-1 text-sm font-medium'>
                    {item.title || `${item.neighborhood || 'موقعیت نامشخص'}`}
                  </span>
                  <span className='text-muted-foreground line-clamp-1 text-xs'>
                    {[item.neighborhood, item.city].filter(Boolean).join('، ')}
                    {item.area !== null && ` · ${item.area} متر`}
                  </span>
                </div>
                <div className='shrink-0 text-left'>
                  <span className='block text-sm font-medium tabular-nums'>
                    {item.total_price !== null ? formatToman(item.total_price) : '—'}
                  </span>
                  {item.source && (
                    <span className='text-muted-foreground text-[10px]'>
                      {leadSourceBadge(item.source)}
                    </span>
                  )}
                </div>
              </button>
            ))}
        </div>

        {!isPending && !debouncedQuery && (
          <p className='text-muted-foreground text-[11px]'>
            از مجموع {new Intl.NumberFormat('fa-IR').format(total)} آگهی، جدیدترین‌ها نخست آمده‌اند.
          </p>
        )}

        <DialogFooter>
          <Button variant='secondary' onClick={() => setOpen(false)}>
            بستن
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default NewLeadDialog;
