"use client";

import PageContainer from '@/components/layout/page-container';
import { Button } from '@/components/ui/button';
import { BoardStatsStrip } from './board-stats-strip';
import { BoardToolbar, EMPTY_FILTERS, matchesFilters, type BoardFilters } from './board-toolbar';
import { LeadBoard } from './lead-board';
import { LeadDetailDrawer } from './lead-detail-drawer';
import { LostLeadsDrawer } from './lost-leads-drawer';
import { NewLeadDialog } from './new-lead-dialog';
import { LEAD_SOURCE_LABELS, PROPERTY_SOURCES } from '../types';
import * as React from 'react';
import { Icons } from '@/components/icons';
import { useLeads } from '../hooks';
import type { Actor } from '../types';


/**
 * Provenance legend.
 *
 * Precedence is not decorative: `INTERNAL_USER` outranks a portal scrape in the
 * deduplicator, so a broker judging whether to trust a card reads this row
 * before the price. The audit note is here for the same reason -- moving a
 * card is not a local UI effect, it is an audited state-machine transition.
 *
 * `DELTA` is not listed: the backend `PropertySource` enum has no such member,
 * so there is no data behind it. Adding the portal is a backend enum change
 * first, and the legend picks it up automatically from PROPERTY_SOURCES.
 */
function SourceLegend() {
  return (
    <div className='border-border bg-card/60 mb-4 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border px-4 py-3 text-xs backdrop-blur-xl'>
      <span className='text-muted-foreground font-medium'>◆ راهنما</span>
      {PROPERTY_SOURCES.map((source) => (
        <span key={source} className='text-muted-foreground'>
          {LEAD_SOURCE_LABELS[source]}
        </span>
      ))}
      <span className='text-muted-foreground/70 mr-auto'>انتقال‌ها با ممیزی (Audit) ثبت می‌شوند</span>
    </div>
  );
}

/**
 * The broker desk.
 *
 * The acting role/tier is passed explicitly for now, because node auth is still
 * the commercial-licence guard; once the OIDC session lands this becomes the
 * session claims.
 */
export default function CrmBoardPage() {
  // The board runs as ADMIN on purpose. `assert_transition_allowed` only lets
  // ADMIN reopen LOST_ARCHIVED, so an AGENT view could list the archive but
  // never restore from it -- a control that is always disabled is worse than
  // one that is honestly scoped to a manager's desk.
  const actor: Actor = { role: 'ADMIN', tier: 'PRO' };

  const [filters, setFilters] = React.useState<BoardFilters>(EMPTY_FILTERS);
  // The open lead is held by id, not by card: the sheet then always renders the
  // server's current copy, even if the card was dragged in the meantime.
  const [openLeadId, setOpenLeadId] = React.useState<string | null>(null);

  // Same query key as the board's own feed, so this is a cache read rather than
  // a second request -- it exists only to give the toolbar an honest count.
  const { data } = useLeads({}, actor);
  const all = data?.items ?? [];
  const visible = React.useMemo(
    () => all.filter((lead) => matchesFilters(lead, filters)).length,
    [all, filters]
  );

  return (
    <PageContainer
      pageTitle='تخته کانبان لیدها'
      pageDescription='پنج مرحله از فایل جدید تا معاملهٔ موفق.'
      pageHeaderAction={
        <div className='flex items-center gap-2'>
          <LostLeadsDrawer actor={actor} />
          <NewLeadDialog actor={actor} />
        </div>
      }
    >
      <BoardStatsStrip actor={actor} />
      <BoardToolbar
        filters={filters}
        onChange={setFilters}
        visible={visible}
        total={all.length}
      />
      <SourceLegend />
      <LeadBoard actor={actor} filters={filters} onOpenLead={setOpenLeadId} />
      <LeadDetailDrawer
        leadId={openLeadId}
        actor={actor}
        onClose={() => setOpenLeadId(null)}
      />
    </PageContainer>
  );
}
