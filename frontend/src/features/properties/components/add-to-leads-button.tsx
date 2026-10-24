'use client';

import * as React from 'react';
import { Icons } from '@/components/icons';
import { useCreateLead } from '@/features/crm/hooks';
import { cn } from '@/lib/utils';
import type { PropertySummary } from '../types';

/**
 * Put one listing on the CRM board.
 *
 * The feed is where an advisor spots the file worth working — a mismarked
 * price, a district they know is soft — so the action belongs on the card
 * rather than a page away in the CRM. Without it the only way in was to
 * remember the listing, switch screens, and find it again in a search box
 * over thousands of rows.
 *
 * Sits in a strip *beneath* the card's content, as a sibling of its ``<Link>``,
 * on purpose: a button inside that anchor is invalid HTML, and the click would
 * navigate to the listing instead of adding the lead.
 *
 * Idempotent server-side (a second POST returns ``created=false``), so the
 * button can stay enabled rather than tracking local state — a double click is
 * a no-op the toast explains, not an error.
 */
export function AddToLeadsButton({ property }: { property: PropertySummary }) {
  const createLead = useCreateLead();
  // Set only by a *successful* add, never by an optimistic guess: the card says
  // "روی میز کار" once the row is really there, and the toast already carries
  // the idempotency message ("از قبل روی تخته بود").
  const [added, setAdded] = React.useState<string | null>(null);
  const onDesk = added === property.id;

  const onAdd = React.useCallback(
    (event: React.MouseEvent<HTMLButtonElement>) => {
      // The card is an anchor; without this the browser follows the link to
      // the listing instead of adding the lead.
      event.preventDefault();
      event.stopPropagation();
      createLead.mutate(property.id, { onSuccess: () => setAdded(property.id) });
    },
    [createLead, property.id]
  );

  return (
    <button
      type='button'
      onClick={onAdd}
      disabled={createLead.isPending}
      aria-label={
        onDesk ? 'این آگهی روی میز کار است' : `افزودن ${property.title || 'این آگهی'} به لیدهای من`
      }
      title={onDesk ? 'روی میز کار' : 'افزودن به لیدهای من'}
      className={cn(
        /* Theme tokens, not the card's fixed pale hexes: those exist for text
           sitting over the *dark thumbnail* and are swapped to theme colours by
           the light-mode block. This strip sits on the card's own surface, so
           `text-muted-foreground` resolves correctly in both modes on its own
           and needs no override. `text-gold-primary` does get the light-mode
           treatment (→ --gold-dark) because the rule is scoped to `.lux-card`. */
        'flex h-8 w-full items-center justify-center gap-1.5 rounded-lg border text-[11px] font-semibold transition-colors',
        'border-border bg-muted/40 text-muted-foreground',
        'hover:border-gold-accent/55 hover:bg-gold-accent/10 hover:text-gold-primary',
        'focus-visible:ring-gold-accent focus-visible:ring-2 focus-visible:outline-none',
        'disabled:cursor-not-allowed disabled:opacity-60',
        onDesk && 'border-gold-accent/45 bg-gold-accent/10 text-gold-primary'
      )}
    >
      {createLead.isPending ? (
        <Icons.spinner className='size-3.5 shrink-0 animate-spin' aria-hidden />
      ) : onDesk ? (
        <Icons.check className='size-3.5 shrink-0' aria-hidden />
      ) : (
        <Icons.add className='size-3.5 shrink-0' aria-hidden />
      )}
      <span className='whitespace-nowrap'>{onDesk ? 'روی میز کار' : 'افزودن به لیدها'}</span>
    </button>
  );
}

export default AddToLeadsButton;
