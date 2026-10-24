'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { IconBuilding, IconCheck, IconPlus, IconX } from '@tabler/icons-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';

import { useAuthContext } from '@/hooks/use-auth';
import {
  useAgencies,
  useCooperations,
  useCreateCooperation,
  useDecideCooperation,
  networkKeys
} from '@/features/network/hooks';
import {
  CooperationStatusBadge,
  formatJalali,
  ListEmpty,
  ListError,
  ListSkeleton
} from '@/features/network/components/shared';
import {
  COOPERATION_SCOPE_LABELS,
  type Cooperation,
  type CooperationScope
} from '@/features/network/types';

/**
 * درخواست‌های همکاری — دریافتی و ارسالی، با تأیید/رد.
 * به `/network/cooperations?agency_id=…` متصل است.
 */
export function RequestsView() {
  const auth = useAuthContext();
  const router = useRouter();
  const queryClient = useQueryClient();
  const agencyId = auth.tenantId;

  const incoming = useCooperations(agencyId, { direction: 'incoming' });
  const outgoing = useCooperations(agencyId, { direction: 'outgoing' });
  const decide = useDecideCooperation();

  const invalidate = () => {
    if (agencyId) {
      void queryClient.invalidateQueries({ queryKey: networkKeys.cooperations(agencyId, { direction: 'incoming' }) });
      void queryClient.invalidateQueries({ queryKey: networkKeys.cooperations(agencyId, { direction: 'outgoing' }) });
    }
  };

  const onDecide = (id: string, decision: 'approve' | 'reject') => {
    if (!agencyId) return;
    decide.mutate(
      { cooperationId: id, decision, agencyId },
      { onSuccess: invalidate }
    );
  };

  if (!agencyId) {
    return (
      <ListEmpty
        title='دفتر شما شناسایی نشد'
        description='برای دیدن درخواست‌های همکاری، باید با حساب دفتر وارد شده باشید.'
        action={<Button onClick={() => router.push('/dashboard/network/agencies')}>رفتن به دفاتر همکار</Button>}
      />
    );
  }

  return (
    <div className='space-y-5'>
      <div className='flex justify-end'>
        <SendRequestDialog agencyId={agencyId} onSent={invalidate} />
      </div>

      <Tabs defaultValue='incoming'>
        <TabsList>
          <TabsTrigger value='incoming'>دریافتی</TabsTrigger>
          <TabsTrigger value='outgoing'>ارسالی</TabsTrigger>
        </TabsList>

        <TabsContent value='incoming' className='mt-4'>
          {incoming.isPending ? (
            <ListSkeleton rows={4} />
          ) : incoming.isError ? (
            <ListError onRetry={() => void incoming.refetch()} />
          ) : (incoming.data?.length ?? 0) === 0 ? (
            <ListEmpty title='درخواست دریافتی ندارید' description='وقتی دفتری برای شما درخواست همکاری بفرستد، اینجا نمایش داده می‌شود.' />
          ) : (
            <div className='space-y-3'>
              {incoming.data!.map((c) => (
                <CooperationRow key={c.id} c={c} showActions onDecide={onDecide} pending={decide.isPending} />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value='outgoing' className='mt-4'>
          {outgoing.isPending ? (
            <ListSkeleton rows={4} />
          ) : outgoing.isError ? (
            <ListError onRetry={() => void outgoing.refetch()} />
          ) : (outgoing.data?.length ?? 0) === 0 ? (
            <ListEmpty title='درخواست ارسالی ندارید' description='از فهرست دفاتر همکار، درخواست جدید بفرستید.' />
          ) : (
            <div className='space-y-3'>
              {outgoing.data!.map((c) => (
                <CooperationRow key={c.id} c={c} />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function CooperationRow({
  c,
  showActions,
  onDecide,
  pending
}: {
  c: Cooperation;
  showActions?: boolean;
  onDecide?: (id: string, d: 'approve' | 'reject') => void;
  pending?: boolean;
}) {
  const canDecide = showActions && c.status === 'PENDING';
  const scopeLabel = (c.scope && COOPERATION_SCOPE_LABELS[c.scope as keyof typeof COOPERATION_SCOPE_LABELS]) ?? c.scope ?? '—';
  return (
    <Card>
      <CardContent className='flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between'>
        <div className='space-y-1'>
          <div className='flex items-center gap-2'>
            <IconBuilding className='h-4 w-4 text-primary' />
            <span className='font-medium' dir='auto'>
              {scopeLabel}
            </span>
          </div>
          <p className='text-xs text-muted-foreground'>
            پورسانت پیش‌فرض {c.default_commission_pct ?? '—'}٪ · ارسال‌شده در {formatJalali(c.created_at)}
          </p>
          {c.expires_at ? (
            <p className='text-xs text-muted-foreground'>تا {formatJalali(c.expires_at)} معتبر است</p>
          ) : null}
          {c.decision_reason ? (
            <p className='text-xs text-muted-foreground'>«{c.decision_reason}»</p>
          ) : null}
        </div>
        <div className='flex items-center gap-2'>
          <CooperationStatusBadge status={c.status} />
          {canDecide && onDecide ? (
            <>
              <Button size='sm' variant='outline' disabled={pending} onClick={() => onDecide(c.id, 'approve')}>
                <IconCheck className='ml-1 h-3.5 w-3.5' />
                تأیید
              </Button>
              <Button size='sm' variant='destructive' disabled={pending} onClick={() => onDecide(c.id, 'reject')}>
                <IconX className='ml-1 h-3.5 w-3.5' />
                رد
              </Button>
            </>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

function SendRequestDialog({ agencyId, onSent }: { agencyId: string; onSent: () => void }) {
  const [open, setOpen] = React.useState(false);
  const [targetId, setTargetId] = React.useState('');
  const [scope, setScope] = React.useState<CooperationScope>('SHARE_LISTINGS');
  const [pct, setPct] = React.useState(50);

  const agencies = useAgencies();
  const create = useCreateCooperation();

  const partners = (agencies.data ?? []).filter((a) => a && a.id !== agencyId);

  const submit = () => {
    if (!targetId) return;
    create.mutate(
      { requester_agency_id: agencyId, target_agency_id: targetId, scope, default_commission_pct: pct, expires_in_days: 30 },
      {
        onSuccess: () => {
          setOpen(false);
          setTargetId('');
          onSent();
        }
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button />}>
        <IconPlus className='ml-1 h-4 w-4' />
        درخواست همکاری جدید
      </DialogTrigger>
      <DialogContent className='sm:max-w-md'>
        <DialogHeader>
          <DialogTitle>ارسال درخواست همکاری</DialogTitle>
          <DialogDescription>دفتر هدف و نوع همکاری را انتخاب کنید.</DialogDescription>
        </DialogHeader>
        <div className='space-y-4'>
          <div className='space-y-2'>
            <Label>دفتر هدف</Label>
            <Select value={targetId} onValueChange={(value) => setTargetId(value ?? '')}>
              <SelectTrigger>
                <SelectValue placeholder='انتخاب دفتر…' />
              </SelectTrigger>
              <SelectContent>
                {partners.map((a) => (
                  <SelectItem key={a.id} value={a.id}>
                    {a.name_fa || a.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className='space-y-2'>
            <Label>نوع همکاری</Label>
            <Select value={scope} onValueChange={(v) => setScope(v as CooperationScope)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(COOPERATION_SCOPE_LABELS) as CooperationScope[]).map((s) => (
                  <SelectItem key={s} value={s}>
                    {COOPERATION_SCOPE_LABELS[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className='space-y-2'>
            <Label>پورسانت پیش‌فرض (٪)</Label>
            <Input type='number' min={0} max={100} value={pct} onChange={(e) => setPct(Number(e.target.value))} />
          </div>
        </div>
        <DialogFooter>
          <Button variant='outline' onClick={() => setOpen(false)}>انصراف</Button>
          <Button onClick={submit} disabled={!targetId || create.isPending}>ارسال درخواست</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
