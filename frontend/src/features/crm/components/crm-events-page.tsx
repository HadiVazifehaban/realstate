"use client";

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import PageContainer from '@/components/layout/page-container';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { addInteraction, fetchLead } from '@/features/crm/api/client';
import {
  INTERACTION_LABELS,
  INTERACTION_TYPES,
  type Actor,
  type InteractionType
} from '@/features/crm/types';

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return new Intl.DateTimeFormat("fa-IR", {
    dateStyle: "short",
    timeStyle: "short"
  }).format(parsed);
}

/**
 * Visits are CRM interactions, not a field on the listing — `VISIT_EVENT` is the
 * only type that carries an appointment time, and there is no `visit_date`
 * anywhere in the schema.
 */
export default function CrmEventsPage() {
  const [actor] = useState<Actor>({ role: "AGENT", tier: "PRO" });
  const [leadId, setLeadId] = useState("");
  const [activeLead, setActiveLead] = useState("");
  const [note, setNote] = useState("");
  const [interactionType, setInteractionType] = useState<InteractionType>("PHONE_CALL");
  const [scheduledAt, setScheduledAt] = useState("");

  const queryClient = useQueryClient();

  const lead = useQuery({
    queryKey: ["crm", "lead", activeLead],
    queryFn: () => fetchLead(activeLead, actor),
    enabled: activeLead.length > 0
  });

  const addEvent = useMutation({
    mutationFn: () =>
      addInteraction(
        activeLead,
        {
          interaction_type: interactionType,
          note: note.trim() || undefined,
          scheduled_at:
            interactionType ==='VISIT_EVENT' && scheduledAt
              ? new Date(scheduledAt).toISOString()
              : null
        },
        actor
      ),
    onSuccess: async () => {
      setNote("");
      setScheduledAt("");
      await queryClient.invalidateQueries({ queryKey: ["crm", "lead", activeLead] });
    }
  });

  return (
    <PageContainer
      pageTitle='رویدادهای CRM'
      pageDescription='ثبت رویداد در یک فرم'
    >
      <div className='space-y-4'>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">ثبت رویداد</CardTitle>
            <CardDescription>شناسهٔ لید را وارد کنید و جزئیات رویداد را تکمیل نمایید.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="lead-id">شناسهٔ لید</Label>
              <Input
                id="lead-id"
                value={leadId}
                onChange={(e) => setLeadId(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') setActiveLead(leadId.trim());
                }}
                placeholder="لید-۱۲۳"
                dir="ltr"
              />
              <Button
                onClick={() => setActiveLead(leadId.trim())}
                disabled={leadId.trim().length === 0}
                size="sm"
              >
                بارگذاری لید
              </Button>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="event-type">نوع رویداد</Label>
                <Select
                  value={interactionType}
                  onValueChange={(value) => setInteractionType(value as InteractionType)}
                >
                  <SelectTrigger id="event-type">
                    {/* Written out, not left to Radix: until the list is opened
                        once there is no selected item to read a label from, and
                        the raw enum («PHONE_CALL») would show instead. */}
                    <SelectValue>{INTERACTION_LABELS[interactionType]}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {INTERACTION_TYPES.map((type) => (
                      <SelectItem key={type} value={type}>
                        {INTERACTION_LABELS[type]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="event-at">زمان بازدید</Label>
                <Input
                  id="event-at"
                  type="datetime-local"
                  value={scheduledAt}
                  onChange={(e) => setScheduledAt(e.target.value)}
                  disabled={interactionType !== 'VISIT_EVENT'}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="event-note">توضیح</Label>
              <Input
                id="event-note"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="توضیح کوتاه"
              />
            </div>

            {addEvent.error && (
              <Alert variant="destructive">
                <AlertTitle>ثبت رویداد ناموفق بود</AlertTitle>
                <AlertDescription>{(addEvent.error as Error).message}</AlertDescription>
              </Alert>
            )}

            <Button
              onClick={() => addEvent.mutate()}
              disabled={activeLead.length === 0 || addEvent.isPending}
            >
              {addEvent.isPending ? 'در حال ثبت…' : 'ثبت رویداد'}
            </Button>
          </CardContent>
        </Card>
        <Card className='lg:col-span-2'>
          <CardHeader>
            <CardTitle className='text-base'>تایم‌لاین رویدادها</CardTitle>
            <CardDescription>
              {lead.data
                ? `${lead.data.lead.title} — ${lead.data.lead.neighborhood}`
                : "لیدی انتخاب نشده است."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {lead.isPending && <Skeleton className='h-40' />}

            {lead.error && (
              <Alert variant='destructive'>
                <AlertTitle>دریافت لید ناموفق بود</AlertTitle>
                <AlertDescription>{(lead.error as Error).message}</AlertDescription>
              </Alert>
            )}

            {lead.data && lead.data.timeline.length === 0 && (
              <p className='text-muted-foreground py-8 text-center text-sm'>
                رویدادی ثبت نشده است.
              </p>
            )}

            {lead.data && lead.data.timeline.length > 0 && (
              <ol className='space-y-3'>
                {lead.data.timeline.map((item) => (
                  <li
                    key={item.id}
                    className='border-border flex flex-wrap items-center gap-3 rounded-lg border p-3'
                  >
                    <Badge variant='secondary'>
                      {INTERACTION_LABELS[item.interaction_type] ?? item.interaction_type}
                    </Badge>
                    <span className='flex-1 text-sm'>{item.note ?? "—"}</span>
                    <span className='text-muted-foreground font-mono text-xs'>
                      {item.scheduled_at
                        ? formatTimestamp(item.scheduled_at)
                        : formatTimestamp(item.created_at)}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </CardContent>
        </Card>
      </div>


    </PageContainer>
  );
}
