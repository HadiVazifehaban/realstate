"use client";

import * as React from 'react';
import { toast } from 'sonner';
import { Icons } from '@/components/icons';
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import { KanbanColumn, KanbanItem } from '@/components/ui/kanban';
import { cn, formatToman } from '@/lib/utils';
import type { Actor, LeadStage, LeadSummary } from '../types';
import {
  leadSourceBadge,
  LEAD_STAGE_LABELS,
  LEAD_TRANSITIONS,
  STAGE_ACCENTS
} from '../types';
import { useDeleteLead } from '../hooks';

interface LeadCardProps {
  lead: LeadSummary;
  /**
   * Stage move, called with the target stage.
   *
   * The card offers this explicitly because drag-and-drop alone is not a
   * reachable way to advance a deal: it needs a fine pointer, and it is
   * unavailable to keyboard and touch users entirely. The menu is the
   * accessible path to the same state machine the drag writes to.
   */
  onMove?: (leadId: string, target: LeadStage) => void;
  /**
   * Open the lead's detail sheet.
   *
   * The card itself is a dnd-kit drag handle, so the sheet is opened from an
   * explicit control in the card's footer rather than from a click on the body:
   * a pointer-down that both starts a drag and opens a panel makes every
   * attempt to nudge a card pop a sheet.
   */
  onOpen?: (leadId: string) => void;
  /** Used to gate the permanent purge server-side. */
  actor?: Actor;
  /**
   * Make the whole card the drag handle.
   *
   * `KanbanItem` only wires the dnd-kit listeners onto the element when this is
   * set -- without it the card renders but is inert, and the board looks
   * plausible while accepting no drops at all. Must stay off inside the drag
   * overlay: there the card is a floating preview, and re-registering a
   * sortable for it would start a nested drag.
   */
  asHandle?: boolean;
}

/**
 * One card on the board.
 *
 * Deliberately shows no owner contact: the phone requires an audited vault
 * reveal, which is a separate, quota-consuming action on the lead detail.
 */
export function LeadCard({ lead, onMove, onOpen, actor, asHandle = true }: LeadCardProps) {
  const location = [lead.neighborhood, lead.city].filter(Boolean).join("، ");
  const accent = STAGE_ACCENTS[lead.stage];

  // Only the transitions the server accepts are offered, so the menu cannot
  // present an action that would come back as a 409.
  const targets = LEAD_TRANSITIONS[lead.stage] ?? [];

  return (
    // Both the stage menu and the purge dialog render their popup through a
    // portal to `document.body`. Inside `KanbanItem` that popup lands inside
    // the dnd-kit sortable node, and opening it crashes the board -- so the
    // interactive chrome is hoisted into a sibling wrapper and only the static
    // card body goes through the sortable.
    <div>
      <KanbanItem
        value={lead.id}
        asHandle={asHandle}
        render={
          <div
            style={
              {
                '--card-accent': accent.stripe,
                '--card-wash': accent.tint,
                // RTL: the accent stripe belongs on the inline-start edge, which
                // is the right in Persian. Logical property keeps it correct if
                // the shell is ever flipped to LTR.
                borderInlineStartColor: 'var(--card-accent)'
              } as React.CSSProperties
            }
            className={cn(
              'crm-lead-card bg-card rounded-md border p-3 shadow-xs',
              lead.is_bargain && 'ring-primary/50 border-primary/40 ring-2'
            )}
          />
        }
      >
        <div className='flex flex-col gap-2'>
          <div className='flex items-start justify-between gap-2'>
            <span className='line-clamp-2 text-sm font-medium'>
              {lead.title || `ملک در ${location || "موقعیت نامشخص"}`}
            </span>
            {lead.is_bargain && (
              <Badge variant='default' className='pointer-events-none shrink-0 rounded-sm'>
                <Icons.trendingDown />
                شکار
              </Badge>
            )}
          </div>

          <span className='text-muted-foreground line-clamp-1 text-xs'>
            {location || "موقعیت نامشخص"}
          </span>

          {leadSourceBadge(lead.source) && (
            <Badge
              variant='outline'
              className='text-muted-foreground pointer-events-none w-fit shrink-0 rounded-sm text-[10px]'
            >
              {leadSourceBadge(lead.source)}
            </Badge>
          )}

          <div className='flex items-center justify-between text-xs'>
            <span className='tabular-nums font-medium'>{formatToman(lead.total_price)}</span>
            <span className='text-muted-foreground tabular-nums'>
              {lead.area !== null && `${lead.area.toLocaleString("en-US")} متر`}
            </span>
          </div>
        </div>
      </KanbanItem>

      {(onMove || onOpen) && (
        <div className='mt-1 space-y-1'>
          {onOpen && (
            <Button
              variant='ghost'
              size='sm'
              className='border-border/60 h-7 w-full justify-center border-t text-xs'
              onClick={() => onOpen(lead.id)}
            >
              <Icons.page className='size-3.5' />
              جزئیات و تایم‌لاین
            </Button>
          )}

          {onMove && targets.length > 0 && (
            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <Button variant='ghost' size='sm' className='border-border/60 h-7 w-full justify-between border-t px-2 text-xs' />
                }
              >
                انتقال مرحله
                <Icons.chevronDown className='size-3.5' />
              </DropdownMenuTrigger>
              <DropdownMenuContent align='start' className='w-48'>
                {/* `DropdownMenuLabel` renders Base UI's Menu.GroupLabel, which
                    reads MenuGroupRootContext and throws error #31 when there is
                    no Group ancestor -- taking the whole board down in a
                    production build. Hence the wrapper. */}
                <DropdownMenuGroup>
                  <DropdownMenuLabel>انتقال به</DropdownMenuLabel>
                </DropdownMenuGroup>
                <DropdownMenuSeparator />
                {targets.map((target) => (
                  <DropdownMenuItem
                    key={target}
                    onClick={() => {
                      if (target === 'LOST_ARCHIVED') {
                        toast.warning(
                          'با انتقال به «از دست رفته»، این لید از تخته خارج می‌شود.'
                        );
                      }
                      onMove(lead.id, target);
                    }}
                  >
                    {LEAD_STAGE_LABELS[target]}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}

          {/* Purge lives outside the stage menu: it is not a transition, and
              burying an irreversible action among reversible ones is how data
              gets destroyed by a mis-click. */}
          {onMove && <DeleteLeadDialog lead={lead} actor={actor} onMove={onMove} />}
        </div>
      )}
    </div>
  );
}

/**
 * Two-step confirmation for the irreversible purge.
 *
 * Step 1 names the softer option first — moving to «از دست رفته» keeps the
 * negotiation history and can be undone. The destructive button is the
 * exception, visually and last, so the common case never requires reading the
 * warning at all.
 *
 * The lead's property is untouched by the purge, so the listing stays in the
 * inventory; only this card and its timeline are lost. Worth saying out loud,
 * because "حذف" on a desk usually implies both.
 */
export function DeleteLeadDialog({
  lead,
  actor,
  onMove
}: {
  lead: LeadSummary;
  actor?: Actor;
  /** Offered in step 1 as the reversible alternative. */
  onMove: (leadId: string, target: 'LOST_ARCHIVED') => void;
}) {
  const [open, setOpen] = React.useState(false);
  const deleteLead = useDeleteLead(actor);

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger
        render={<Button variant='ghost' size='sm' className='text-destructive h-7 w-full text-xs' />}
      >
        حذف کارت
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>حذف این لید</AlertDialogTitle>
          {/* Plain text only: AlertDialogDescription renders a <p>, so any
              block element inside it is invalid HTML and React logs the
              nesting mismatch. The detail belongs in sibling paragraphs. */}
          <AlertDialogDescription>
            برای «{lead.title || 'این لید'}» دو گزینه دارید. حذف دائمی برگشت‌پذیر
            نیست.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>انصراف</AlertDialogCancel>
          <Button
            variant='secondary'
            onClick={() => {
              onMove(lead.id, 'LOST_ARCHIVED');
              setOpen(false);
            }}
          >
            انتقال به «از دست رفته»
          </Button>
          <Button
            variant='destructive'
            disabled={deleteLead.isPending}
            onClick={() => {
              // No preventDefault: `AlertDialogAction` is a plain Button with no
              // auto-close wiring, so this handler owns the dialog lifecycle and
              // must close it itself -- but only once the server has agreed, so
              // a failure leaves the broker able to retry.
              deleteLead.mutate(lead.id, { onSuccess: () => setOpen(false) });
            }}
          >
            {deleteLead.isPending ? 'در حال حذف…' : 'حذف دائمی'}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

interface LeadColumnProps extends Omit<React.ComponentProps<typeof KanbanColumn>, "children"> {
  /** Stage id, used to tint the column rule. */
  stage: LeadStage;
  label: string;
  leads: LeadSummary[];
  onMoveLead?: (leadId: string, target: LeadStage) => void;
  onOpenLead?: (leadId: string) => void;
  actor?: Actor;
}

/** One board column, heading included. */
export function LeadColumn({
  stage,
  label,
  leads,
  onMoveLead,
  onOpenLead,
  actor,
  ...props
}: LeadColumnProps) {
  return (
    <KanbanColumn
      {...props}
      style={{ '--column-accent': STAGE_ACCENTS[stage].stripe } as React.CSSProperties}
      className='crm-lead-column w-full shrink-0 md:w-[300px]'
    >
      <div className='flex items-center justify-between'>
        <span className='text-sm font-semibold'>{label}</span>
        <Badge variant='secondary' className='pointer-events-none rounded-sm'>
          {leads.length}
        </Badge>
      </div>
      <div className='flex flex-col gap-2 p-0.5'>
        {leads.map((lead) => (
          <LeadCard
            key={lead.id}
            lead={lead}
            onMove={onMoveLead}
            onOpen={onOpenLead}
            actor={actor}
          />
        ))}
      </div>
    </KanbanColumn>
  );
}
