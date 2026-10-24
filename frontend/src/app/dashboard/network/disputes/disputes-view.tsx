'use client';

import * as React from 'react';
import { IconGavel } from '@tabler/icons-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';

import { useAuthContext } from '@/hooks/use-auth';
import {
  useAddDisputeMessage,
  useDispute,
  useDisputes,
  useUpdateDisputeStatus
} from '@/features/network/hooks';
import {
  DisputeStatusBadge,
  formatJalaliDateTime,
  ListEmpty,
  ListError,
  ListSkeleton
} from '@/features/network/components/shared';
import {
  DISPUTE_CATEGORY_LABELS,
  DISPUTE_STATUS_LABELS,
  type Dispute,
  type DisputeStatus
} from '@/features/network/types';

const STATUS_FLOW: DisputeStatus[] = ['UNDER_REVIEW', 'WAITING_RESPONSE', 'RESOLVED', 'REJECTED', 'ESCALATED'];

/**
 * اختلافات بین دفاتر — به `/network/disputes` متصل است.
 * نمایش فهرست، باز کردن جزئیات با تایم‌لاین پیام و تغییر وضعیت.
 */
export function DisputesView() {
  const auth = useAuthContext();
  const agencyId = auth.tenantId;
  const [openId, setOpenId] = React.useState<string | null>(null);

  const disputes = useDisputes({ agencyId });

  if (!agencyId) {
    return <ListEmpty title='دفتر شما شناسایی نشد' description='برای دیدن اختلافات، باید با حساب دفتر وارد شده باشید.' />;
  }

  if (disputes.isPending) return <ListSkeleton rows={5} />;
  if (disputes.isError) return <ListError onRetry={() => void disputes.refetch()} />;
  if ((disputes.data?.length ?? 0) === 0) {
    return (
      <ListEmpty
        title='اختلافی ثبت نشده'
        description='اگر بر سر کمیسیون، مالکیت فایل یا دسترسی با دفتر دیگر اختلاف دارید، آن را ثبت کنید.'
      />
    );
  }

  return (
    <div className='space-y-3'>
      {disputes.data!.map((d) => (
        <DisputeRow key={d.id} d={d} onOpen={() => setOpenId(d.id)} />
      ))}
      <DisputeDetailDialog disputeId={openId} onOpenChange={(v) => !v && setOpenId(null)} />
    </div>
  );
}

function DisputeRow({ d, onOpen }: { d: Dispute; onOpen: () => void }) {
  return (
    <Card>
      <CardContent className='flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between'>
        <div className='space-y-1'>
          <div className='flex flex-wrap items-center gap-2'>
            <IconGavel className='h-4 w-4 text-primary' />
            <span className='font-medium' dir='auto'>{d.title}</span>
            <Badge variant='secondary'>{DISPUTE_CATEGORY_LABELS[d.category] ?? d.category}</Badge>
            <DisputeStatusBadge status={d.status} />
          </div>
          <p className='text-xs text-muted-foreground'>
            {formatJalaliDateTime(d.created_at)}
            {d.resolved_at ? ` · حل‌شده ${formatJalaliDateTime(d.resolved_at)}` : ''}
          </p>
          {d.detail ? <p className='line-clamp-1 text-xs text-muted-foreground' dir='auto'>{d.detail}</p> : null}
        </div>
        <Button size='sm' variant='outline' onClick={onOpen}>جزئیات و پیام‌ها</Button>
      </CardContent>
    </Card>
  );
}

function DisputeDetailDialog({
  disputeId,
  onOpenChange
}: {
  disputeId: string | null;
  onOpenChange: (open: boolean) => void;
}) {
  const detail = useDispute(disputeId);
  const addMessage = useAddDisputeMessage();
  const updateStatus = useUpdateDisputeStatus();
  const [body, setBody] = React.useState('');

  const d = detail.data;

  const submitMessage = () => {
    if (!disputeId || !body.trim()) return;
    addMessage.mutate(
      { disputeId, body: body.trim() },
      {
        onSuccess: () => {
          setBody('');
          void detail.refetch();
        }
      }
    );
  };

  const changeStatus = (status: DisputeStatus) => {
    if (!disputeId) return;
    updateStatus.mutate(
      { disputeId, payload: { status } },
      { onSuccess: () => void detail.refetch() }
    );
  };

  return (
    <Dialog open={!!disputeId} onOpenChange={onOpenChange}>
      <DialogContent className='sm:max-w-lg'>
        <DialogHeader>
          <DialogTitle>جزئیات اختلاف</DialogTitle>
          <DialogDescription>تایم‌لاین، پیام‌ها و وضعیت اختلاف.</DialogDescription>
        </DialogHeader>
        {detail.isPending ? (
          <ListSkeleton rows={4} />
        ) : detail.isError || !d ? (
          <ListError onRetry={() => void detail.refetch()} />
        ) : (
          <div className='space-y-4'>
            <div className='flex items-center gap-2'>
              <span className='font-medium' dir='auto'>{d.title}</span>
              <Badge variant='secondary'>{DISPUTE_CATEGORY_LABELS[d.category] ?? d.category}</Badge>
              <DisputeStatusBadge status={d.status} />
            </div>
            {d.detail ? <p className='text-sm leading-6' dir='auto'>{d.detail}</p> : null}
            {d.resolution ? (
              <p className='rounded border border-border bg-muted/40 p-2 text-sm' dir='auto'>
                نتیجه: {d.resolution}
              </p>
            ) : null}

            <div>
              <h4 className='mb-2 text-sm font-medium'>پیام‌ها</h4>
              {d.messages.length === 0 ? (
                <p className='text-xs text-muted-foreground'>پیامی ثبت نشده است.</p>
              ) : (
                <ul className='space-y-2'>
                  {d.messages.map((m) => (
                    <li key={m.id} className='rounded border border-border p-2 text-sm'>
                      <div className='flex items-center justify-between'>
                        <span className='text-xs text-muted-foreground' dir='auto'>{m.author}</span>
                        <span className='text-[10px] text-muted-foreground'>{formatJalaliDateTime(m.created_at)}</span>
                      </div>
                      <p className='mt-1' dir='auto'>{m.body}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className='space-y-2'>
              <Textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder='افزودن پیام به اختلاف…'
                aria-label='متن پیام'
              />
              <Button size='sm' onClick={submitMessage} disabled={!body.trim() || addMessage.isPending}>
                ثبت پیام
              </Button>
            </div>

            {d.status !== 'RESOLVED' ? (
              <div className='space-y-1'>
                <span className='text-xs text-muted-foreground'>تغییر وضعیت</span>
                <Select value={d.status} onValueChange={(v) => v && changeStatus(v as DisputeStatus)}>
                  <SelectTrigger className='w-full' aria-label='وضعیت اختلاف'>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {STATUS_FLOW.map((s) => (
                      <SelectItem key={s} value={s}>
                        {DISPUTE_STATUS_LABELS[s]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : null}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
