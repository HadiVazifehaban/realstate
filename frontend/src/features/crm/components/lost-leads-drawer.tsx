'use client';

import * as React from 'react';
import { Icons } from '@/components/icons';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty';
import { Skeleton } from '@/components/ui/skeleton';
import { LEAD_STAGE_LABELS, leadSourceBadge } from '../types';
import { useLeads, useMoveLead } from '../hooks';
import type { Actor, LeadSummary } from '../types';
import { formatToman } from '@/lib/utils';

/**
 * Archive drawer for leads parked in LOST_ARCHIVED.
 *
 * The five board columns deliberately exclude the terminal sink, so an archived
 * lead is off the board entirely -- with no in-product way to find it again.
 * That is the right default (the desk should show live deals) but it makes an
 * archive that cannot be opened indistinguishable from data loss, so this
 * restores the only path back.
 *
 * Reopening is a governance action server-side: `assert_transition_allowed`
 * only lets ADMIN leave LOST_ARCHIVED. The gate is surfaced here too, so a
 * supervisor sees why the button is disabled instead of hitting a 403.
 */
export function LostLeadsDrawer({ actor }: { actor?: Actor }) {
  const [open, setOpen] = React.useState(false);
  const { data, isPending } = useLeads({ stages: ['LOST_ARCHIVED'], limit: 200 }, actor);
  const moveLead = useMoveLead(actor);

  const canRestore = actor?.role === 'ADMIN';
  const archived = data?.items ?? [];

  const restore = (lead: LeadSummary) => {
    moveLead.mutate({
      leadId: lead.id,
      payload: { target_stage: 'NEW_FILE', note: 'بازیابی از بایگانی' }
    });
  };

  return (
    <>
      <Button variant='outline' size='sm' onClick={() => setOpen(true)} aria-expanded={open}>
        <Icons.archive className='size-4' />
        بایگانی لیدها
        {archived.length > 0 && (
          <Badge variant='secondary' className='rounded-sm text-[10px]'>
            {new Intl.NumberFormat('fa-IR').format(archived.length)}
          </Badge>
        )}
      </Button>

      {open && (
        <div className='fixed inset-0 z-50 flex justify-end' role='dialog' aria-modal='true' aria-label='بایگانی لیدها'>
          <button type='button' aria-label='بستن' onClick={() => setOpen(false)} className='absolute inset-0 bg-black/50' />
          <DrawerPanel
            canRestore={canRestore}
            isPending={isPending}
            archived={archived}
            isMutating={moveLead.isPending}
            onClose={() => setOpen(false)}
            onRestore={restore}
          />
        </div>
      )}
    </>
  );
}

function DrawerPanel({
  canRestore,
  isPending,
  archived,
  isMutating,
  onClose,
  onRestore
}: {
  canRestore: boolean;
  isPending: boolean;
  archived: LeadSummary[];
  isMutating: boolean;
  onClose: () => void;
  onRestore: (lead: LeadSummary) => void;
}) {
  return (
    <div className='bg-background relative flex h-full w-full max-w-md flex-col border-l shadow-xl'>
      <header className='border-border flex items-center justify-between border-b p-4'>
        <div>
          <h2 className='text-base font-medium'>لیدهای از دست رفته</h2>
          <p className='text-muted-foreground text-xs'>
            لیدهایی که بایگانی شده‌اند و دیگر روی تخته نیستند.
          </p>
        </div>
        <Button variant='ghost' size='icon' onClick={onClose} aria-label='بستن'>
          <Icons.close className='size-4' />
        </Button>
      </header>

      {!canRestore && (
        <p className='border-destructive/40 bg-destructive/10 text-destructive m-3 rounded-md border p-2 text-xs'>
          بازگردانی لید فقط با نقش مدیر ارشد ممکن است. سایر نقش‌ها می‌توانند لیدها را
          ببینند ولی بازگردانی نیاز به تأیید مدیر دارد.
        </p>
      )}

      <div className='flex-1 space-y-2 overflow-y-auto p-3'>
        {isPending && (
          <>
            <Skeleton className='h-20 w-full' />
            <Skeleton className='h-20 w-full' />
          </>
        )}

        {!isPending && archived.length === 0 && (
          <Empty className='border'>
            <EmptyHeader>
              <Icons.archive className='text-muted-foreground size-6' />
              <EmptyTitle>بایگانی خالی است</EmptyTitle>
              <EmptyDescription>
                هیچ لیدی به «از دست رفته» منتقل نشده است.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}

        {archived.map((lead) => {
          const location = [lead.neighborhood, lead.city].filter(Boolean).join('، ');
          return (
            <div key={lead.id} className='border-border space-y-2 rounded-lg border p-3'>
              <div className='flex items-start justify-between gap-2'>
                <span className='line-clamp-2 text-sm font-medium'>
                  {lead.title || `ملک در ${location || 'موقعیت نامشخص'}`}
                </span>
                {leadSourceBadge(lead.source) && (
                  <Badge variant='outline' className='text-muted-foreground shrink-0 rounded-sm text-[10px]'>
                    {leadSourceBadge(lead.source)}
                  </Badge>
                )}
              </div>
              <p className='text-muted-foreground text-xs'>
                {location || 'موقعیت نامشخص'} · {formatToman(lead.total_price)}
              </p>
              <Button
                size='sm'
                variant='secondary'
                className='w-full'
                disabled={!canRestore || isMutating}
                onClick={() => onRestore(lead)}
              >
                <Icons.restore className='size-4' />
                بازگردانی به «{LEAD_STAGE_LABELS.NEW_FILE}»
              </Button>
            </div>
          );
        })}
      </div>
    </div>
  );
}