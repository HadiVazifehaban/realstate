'use client';

import * as React from 'react';

import { Icons } from '@/components/icons';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { LoadingButton } from '@/components/ui/loading-button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle
} from '@/components/ui/sheet';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { formatToman } from '@/lib/utils';

import { SourceBadge } from './board-toolbar';
import { RevealContactButton } from './reveal-contact-button';
import { useAddInteraction, useLead, useMoveLead } from '../hooks';
import {
  INTERACTION_LABELS,
  INTERACTION_TYPES,
  LEAD_STAGE_LABELS,
  LEAD_TRANSITIONS,
  STAGE_ACCENTS,
  type Actor,
  type InteractionType
} from '../types';

const fa = new Intl.NumberFormat('fa-IR');

const timestampFormatter = new Intl.DateTimeFormat('fa-IR', {
  dateStyle: 'short',
  timeStyle: 'short'
});

function formatWhen(value: string | null): string {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : timestampFormatter.format(parsed);
}

/**
 * Composer options.
 *
 * `STAGE_CHANGED` is excluded: it is written by the transition itself, and a
 * broker typing one by hand would double-log the move and desync the timeline
 * from the board.
 */
const EVENT_TYPE_ITEMS = INTERACTION_TYPES.filter(
  (type) => type !== 'STAGE_CHANGED'
).map((type) => ({ value: type, label: INTERACTION_LABELS[type] }));

const INTERACTION_ICONS: Record<InteractionType, keyof typeof Icons> = {
  PHONE_CALL: 'phone',
  VISIT_EVENT: 'calendar',
  NOTE_ADDED: 'page',
  PRICE_OFFER: 'trendingUp',
  STAGE_CHANGED: 'kanban'
};

/**
 * One deal, opened from the board.
 *
 * The card is a summary of a *listing*; everything a broker actually acts on —
 * the negotiation history, the appointment, the owner's phone — lives here. The
 * phone in particular is never on the card: it costs daily quota and writes an
 * audit row, so it is a deliberate action taken inside this panel rather than
 * something rendered with the column.
 *
 * The sheet owns no filter or board state: it reads the lead by id, so a card
 * dragged in another tab does not leave this panel showing a stale column.
 */
export function LeadDetailDrawer({
  leadId,
  actor,
  onClose
}: {
  leadId: string | null;
  actor?: Actor;
  onClose: () => void;
}) {
  const { data, isPending, isError, error } = useLead(leadId ?? '', actor);
  const moveLead = useMoveLead(actor);

  const stage = data?.lead.stage;
  const targets = stage ? LEAD_TRANSITIONS[stage] : [];

  return (
    <Sheet open={leadId !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side='right' className='sm:max-w-lg'>
        <SheetHeader className='border-border border-b'>
          <SheetTitle>{data?.lead.title || 'جزئیات لید'}</SheetTitle>
          <SheetDescription>
            {data
              ? [data.lead.neighborhood, data.lead.city].filter(Boolean).join('، ') ||
                'موقعیت نامشخص'
              : 'در حال دریافت پرونده…'}
          </SheetDescription>
        </SheetHeader>

        <div className='flex-1 space-y-4 overflow-y-auto p-4'>
          {isPending && (
            <>
              <Skeleton className='h-24 w-full' />
              <Skeleton className='h-40 w-full' />
            </>
          )}

          {isError && (
            <p className='border-destructive/40 bg-destructive/10 text-destructive rounded-md border p-3 text-xs'>
              {(error as Error)?.message ?? 'دریافت پروندهٔ لید ناموفق بود.'}
            </p>
          )}

          {data && (
            <>
              <div className='flex flex-wrap items-center gap-2'>
                <Badge
                  style={
                    {
                      borderInlineStartColor: STAGE_ACCENTS[data.lead.stage].stripe
                    } as React.CSSProperties
                  }
                  variant='secondary'
                  className='rounded-sm border-s-2'
                >
                  {LEAD_STAGE_LABELS[data.lead.stage]}
                </Badge>
                <SourceBadge source={data.lead.source} />
                {data.lead.is_bargain && (
                  <Badge variant='default' className='rounded-sm'>
                    <Icons.trendingDown />
                    شکار
                  </Badge>
                )}
                {data.lead.deviation_pct !== null && (
                  <span className='text-muted-foreground text-xs tabular-nums'>
                    انحراف از ارزش‌گذاری: {fa.format(data.lead.deviation_pct)}٪
                  </span>
                )}
              </div>

              <dl className='grid grid-cols-3 gap-3 text-sm'>
                <Spec label='قیمت' value={formatToman(data.lead.total_price)} />
                <Spec
                  label='متراژ'
                  value={data.lead.area === null ? '—' : `${fa.format(data.lead.area)} متر`}
                />
                <Spec
                  label='خواب'
                  value={data.lead.rooms === null ? '—' : fa.format(data.lead.rooms)}
                />
              </dl>

              <div className='flex flex-wrap items-center gap-2'>
                <Button
                  size='sm'
                  variant='outline'
                  render={<a href={`/dashboard/properties/${data.lead.property_id}`} />}
                >
                  <Icons.externalLink className='size-4' />
                  مشاهدهٔ آگهی
                </Button>
                <span className='text-muted-foreground text-[11px]'>
                  آخرین به‌روزرسانی: {formatWhen(data.lead.updated_at)}
                </span>
              </div>

              <section className='border-border rounded-xl border p-3'>
                <h3 className='mb-2 flex items-center gap-2 text-sm font-medium'>
                  <Icons.phone className='size-4' />
                  تماس با مالک
                </h3>
                <RevealContactButton propertyId={data.lead.property_id} actor={actor} />
              </section>

              {targets.length > 0 && (
                <section className='border-border rounded-xl border p-3'>
                  <h3 className='mb-2 flex items-center gap-2 text-sm font-medium'>
                    <Icons.share className='size-4' />
                    انتقال مرحله
                  </h3>
                  <div className='flex flex-wrap gap-2'>
                    {targets.map((target) => (
                      <Button
                        key={target}
                        size='sm'
                        variant={target === 'LOST_ARCHIVED' ? 'ghost' : 'secondary'}
                        disabled={moveLead.isPending}
                        onClick={() =>
                          moveLead.mutate({ leadId: data.lead.id, payload: { target_stage: target } })
                        }
                      >
                        {target === 'LOST_ARCHIVED' && <Icons.archive className='size-4' />}
                        {LEAD_STAGE_LABELS[target]}
                      </Button>
                    ))}
                  </div>
                </section>
              )}

              <EventComposer leadId={data.lead.id} actor={actor} />

              <Separator />

              <section>
                <h3 className='mb-3 flex items-center gap-2 text-sm font-medium'>
                  <Icons.clock className='size-4' />
                  تایم‌لاین
                </h3>

                {data.timeline.length === 0 ? (
                  <p className='text-muted-foreground py-6 text-center text-xs'>
                    رویدادی ثبت نشده است؛ نخستین تماس یا یادداشت را ثبت کنید.
                  </p>
                ) : (
                  <ol className='space-y-2'>
                    {data.timeline.map((event) => {
                      const Icon = Icons[INTERACTION_ICONS[event.interaction_type]] ?? Icons.page;
                      return (
                        <li
                          key={event.id}
                          className='border-border flex items-start gap-3 rounded-lg border p-2.5'
                        >
                          <Icon className='text-muted-foreground mt-0.5 size-4 shrink-0' />
                          <div className='min-w-0 flex-1'>
                            <div className='flex flex-wrap items-baseline justify-between gap-2'>
                              <span className='text-xs font-medium'>
                                {INTERACTION_LABELS[event.interaction_type]}
                              </span>
                              <span className='text-muted-foreground text-[10px] tabular-nums'>
                                {formatWhen(event.scheduled_at ?? event.created_at)}
                              </span>
                            </div>
                            {event.note && (
                              <p className='text-muted-foreground mt-0.5 text-xs break-words'>
                                {event.note}
                              </p>
                            )}
                            {event.scheduled_at && (
                              <span className='text-muted-foreground text-[10px]'>
                                قرار بازدید ثبت شده است
                              </span>
                            )}
                          </div>
                        </li>
                      );
                    })}
                  </ol>
                )}
              </section>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function Spec({ label, value }: { label: string; value: string }) {
  return (
    <div className='bg-card/60 rounded-lg border px-2.5 py-1.5'>
      <dt className='text-muted-foreground text-[11px]'>{label}</dt>
      <dd className='truncate text-sm font-medium tabular-nums'>{value}</dd>
    </div>
  );
}

/**
 * Record a call, a visit, a note or an offer.
 *
 * The appointment time only appears for `VISIT_EVENT`, because that is the one
 * interaction the schema allows to carry one — offering the field elsewhere
 * would invite a note that looks like a booked visit.
 */
function EventComposer({ leadId, actor }: { leadId: string; actor?: Actor }) {
  const [type, setType] = React.useState<InteractionType>('PHONE_CALL');
  const [note, setNote] = React.useState('');
  const [scheduledAt, setScheduledAt] = React.useState('');
  const addInteraction = useAddInteraction(actor);

  const isVisit = type === 'VISIT_EVENT';
  const canSubmit = !isVisit || scheduledAt.length > 0;

  return (
    <section className='border-border rounded-xl border p-3'>
      <h3 className='mb-3 flex items-center gap-2 text-sm font-medium'>
        <Icons.send className='size-4' />
        ثبت رویداد جدید
      </h3>

      <div className='space-y-3'>
        <div className='grid gap-3 sm:grid-cols-2'>
          <div className='space-y-1.5'>
            <Label htmlFor='crm-event-type'>نوع رویداد</Label>
            <Select
              value={type}
              onValueChange={(value) => setType(value as InteractionType)}
            >
              <SelectTrigger id='crm-event-type' className='w-full'>
                {/* The label is rendered from `type` rather than through
                    `SelectValue`, which would show the raw enum until the
                    popup has been opened at least once. */}
                <span className='flex-1 text-start'>
                  {INTERACTION_LABELS[type] ?? 'انتخاب کنید'}
                </span>
              </SelectTrigger>
              <SelectContent>
                {EVENT_TYPE_ITEMS.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {isVisit && (
            <div className='space-y-1.5'>
              <Label htmlFor='crm-event-at'>زمان بازدید</Label>
              <Input
                id='crm-event-at'
                type='datetime-local'
                value={scheduledAt}
                onChange={(event) => setScheduledAt(event.target.value)}
              />
            </div>
          )}
        </div>

        <div className='space-y-1.5'>
          <Label htmlFor='crm-event-note'>توضیح</Label>
          <Textarea
            id='crm-event-note'
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder='خلاصهٔ تماس یا یادداشت داخلی'
            rows={2}
          />
        </div>

        <LoadingButton
          size='sm'
          loading={addInteraction.isPending}
          disabled={!canSubmit}
          onClick={() =>
            addInteraction.mutate(
              {
                leadId,
                payload: {
                  interaction_type: type,
                  note: note.trim() || undefined,
                  scheduled_at: isVisit ? new Date(scheduledAt).toISOString() : null
                }
              },
              {
                onSuccess: () => {
                  setNote('');
                  setScheduledAt('');
                }
              }
            )
          }
        >
          ثبت رویداد
        </LoadingButton>

        {isVisit && !canSubmit && (
          <p className='text-muted-foreground text-[11px]'>
            رویداد بازدید بدون زمان قرار ثبت نمی‌شود.
          </p>
        )}
      </div>
    </section>
  );
}
