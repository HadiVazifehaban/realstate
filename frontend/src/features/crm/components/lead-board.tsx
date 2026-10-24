"use client";

import * as React from 'react';
import { toast } from 'sonner';
import { Icons } from '@/components/icons';
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty';
import { Kanban, KanbanBoard as KanbanBoardPrimitive, KanbanOverlay } from '@/components/ui/kanban';
import { LeadCard, LeadColumn } from './lead-card';
import { matchesFilters, type BoardFilters } from './board-toolbar';
import { createRestrictToContainer } from '@/features/kanban/utils/restrict-to-container';
import { useLeads, useMoveLead } from '../hooks';
import {
  KANBAN_COLUMNS,
  LEAD_STAGE_LABELS,
  canMoveLead,
  type Actor,
  type LeadStage,
  type LeadSummary
} from '../types';

/**
 * The five-column broker board.
 *
 * Illegal drops are refused locally against `canMoveLead`, so a card can never
 * skip a column; the server re-validates regardless. The optimistic update is
 * reverted on failure, because a board that lies about a deal's stage is worse
 * than one that lags by a second.
 */
export function LeadBoard({
  actor,
  filters,
  onOpenLead
}: {
  actor?: Actor;
  /** Applied client-side: the node returns the whole pipeline in one feed. */
  filters?: BoardFilters;
  onOpenLead?: (leadId: string) => void;
} = {}) {
  const { data, isPending, isError, error } = useLeads({}, actor);
  const moveLead = useMoveLead(actor);
  const containerRef = React.useRef<HTMLDivElement>(null);

  const restrictToBoard = React.useCallback(
    createRestrictToContainer(() => containerRef.current),
    []
  );

  // Filtering is applied to the fetched page, not to `columns`: during a drag
  // the primitive owns `columns`, and re-filtering it mid-flight would make the
  // card under the pointer vanish.
  const leads = React.useMemo(
    () => (filters ? (data?.items ?? []).filter((lead) => matchesFilters(lead, filters)) : (data?.items ?? [])),
    [data, filters]
  );

  // The Kanban primitive is column-keyed, so the board is a plain record.
  // Recomputed from `leads` and mirrored into `columns` below.

  // The Kanban primitive owns `columns` during a drag; it is mirrored here so a
  // change can be diffed against the server copy before being persisted.
  const [columns, setColumns] = React.useState<Record<LeadStage, LeadSummary[]>>(() =>
    nextColumnsFor(leads)
  );
  React.useEffect(() => setColumns(nextColumnsFor(leads)), [leads]);

  /**
   * Persist a stage move.
   *
   * Shared by the drag handler and the per-card menu so both paths hit exactly
   * the same validation and the same server call. The optimistic column update
   * is reverted on failure: a board that shows a deal in the wrong column is
   * worse than one that lags by a second.
   */
  const advance = React.useCallback(
    (leadId: string, from: LeadStage, to: LeadStage, snapshot: Record<LeadStage, LeadSummary[]>) => {
      if (from === to || !canMoveLead(from, to)) {
        setColumns(snapshot);
        toast.error(
          `انتقال از «${LEAD_STAGE_LABELS[from]}» به «${LEAD_STAGE_LABELS[to]}» مجاز نیست.`
        );
        return;
      }

      moveLead.mutate(
        { leadId, payload: { target_stage: to } },
        { onError: () => setColumns(snapshot) }
      );
    },
    [moveLead]
  );

  const handleValueChange = React.useCallback(
    (next: Record<string, LeadSummary[]>) => {
      const previous = columns;
      setColumns(next as Record<LeadStage, LeadSummary[]>);

      // Diff to find the single card that moved, then persist only that change.
      for (const stage of KANBAN_COLUMNS) {
        const before = new Set((previous[stage] ?? []).map((lead) => lead.id));
        const moved = (next[stage] ?? []).filter((lead) => !before.has(lead.id));
        if (moved.length === 0) continue;

        const lead = moved[0]!;
        const from = (Object.keys(previous) as LeadStage[]).find((key) =>
          (previous[key] ?? []).some((item) => item.id === lead.id)
        );

        // Dropping onto a column the card was already in is a no-op, not an
        // illegal move: without this a reorder inside one column would snap
        // back with an error toast.
        if (from === undefined || from === stage) return;

        advance(lead.id, from, stage, previous);
        return;
      }
    },
    [columns, advance]
  );

  /** Menu path: move a card without dragging it. */
  const handleMoveLead = React.useCallback(
    (leadId: string, target: LeadStage) => {
      const snapshot = columns;
      const from = (Object.keys(snapshot) as LeadStage[]).find((key) =>
        (snapshot[key] ?? []).some((item) => item.id === leadId)
      );
      if (from === undefined) return;

      // Optimistic move so the card lands in the new column immediately; the
      // refetch from `useMoveLead` reconciles it with the server's answer.
      setColumns({
        ...snapshot,
        [from]: snapshot[from].filter((item) => item.id !== leadId),
        [target]: [...(snapshot[target] ?? []), snapshot[from].find((item) => item.id === leadId)!]
      });

      advance(leadId, from, target, snapshot);
    },
    [columns, advance]
  );

  if (isPending) {
    return (
      <div className='flex items-center justify-center py-16'>
        <Icons.spinner className='text-muted-foreground size-6 animate-spin' />
        <span className='text-muted-foreground mr-3 text-sm'>در حال دریافت میز کار…</span>
      </div>
    );
  }

  if (isError) {
    return (
      <Empty className='border'>
        <EmptyHeader>
          <Icons.warning className='text-destructive size-6' />
          <EmptyTitle>دریافت لیدها ناموفق بود</EmptyTitle>
          <EmptyDescription>
            {(error as Error)?.message ?? "ارتباط با نود آفیس برقرار نشد."}
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }

  return (
    <div ref={containerRef}>
      <Kanban
        value={columns}
        onValueChange={handleValueChange}
        getItemValue={(lead) => lead.id}
        modifiers={[restrictToBoard]}
        autoScroll={false}
      >
        {/*
          `min-w-0` is load-bearing here: this is a flex item of the page
          container's flex column, and its automatic minimum size is the board's
          min-content (five columns of lead cards). Without the floor-break the
          whole dashboard column grew past the viewport -- the board's own
          `overflow-x-auto` only clips it visually, it does not shrink the page.
        */}
        <div className='w-full min-w-0 overflow-x-auto rounded-md pb-4'>
          <KanbanBoardPrimitive className='flex flex-col items-start gap-4 md:flex-row'>
            {KANBAN_COLUMNS.map((stage) => (
              <LeadColumn
                key={stage}
                value={stage}
                stage={stage}
                label={LEAD_STAGE_LABELS[stage]}
                leads={columns[stage] ?? []}
                onMoveLead={handleMoveLead}
                onOpenLead={onOpenLead}
                actor={actor}
              />
            ))}
          </KanbanBoardPrimitive>
        </div>
        <KanbanOverlay>
          {({ value, variant }) => {
            if (variant ==='column') {
              const stage = value as LeadStage;
              if (!(stage in columns)) return null;
              return (
                <LeadColumn
                  value={stage}
                  stage={stage}
                  label={LEAD_STAGE_LABELS[stage]}
                  leads={columns[stage] ?? []}
                  onMoveLead={handleMoveLead}
                  onOpenLead={onOpenLead}
                  actor={actor}
                />
              );
            }
            const lead = Object.values(columns)
              .flat()
              .find((item) => item.id === value);
            if (!lead) return null;
            // `asHandle` is off here: this is the floating preview shown while dragging,
            // and registering a second sortable for it would nest a drag.
            return <LeadCard lead={lead} onMove={handleMoveLead} actor={actor} asHandle={false} />;
          }}
        </KanbanOverlay>
      </Kanban>
    </div>
  );
}

/** Groups leads into board columns, dropping the terminal sink. */
function nextColumnsFor(leads: LeadSummary[]): Record<LeadStage, LeadSummary[]> {
  const grouped = Object.fromEntries(
    KANBAN_COLUMNS.map((stage) => [stage, [] as LeadSummary[]])
  ) as Record<LeadStage, LeadSummary[]>;
  for (const lead of leads) {
    if (lead.stage in grouped) grouped[lead.stage].push(lead);
  }
  return grouped;
}
