'use client';

import * as React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { IconEyeOff, IconMapPin, IconRefresh, IconTrash } from '@tabler/icons-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger
} from '@/components/ui/alert-dialog';

import { useAuthContext } from '@/hooks/use-auth';
import { useExtendShare, useRevokeShare, useShares } from '@/features/network/hooks';
import {
  formatJalali,
  ListEmpty,
  ListError,
  ListSkeleton,
  ShareStatusBadge
} from '@/features/network/components/shared';
import {
  SHARE_MODE_LABELS,
  type Share,
  type ShareMode,
  type ShareStatus
} from '@/features/network/types';

const STATUS_FILTERS: { value: ShareStatus | 'ALL'; label: string }[] = [
  { value: 'ALL', label: 'همه' },
  { value: 'ACTIVE', label: 'فعال' },
  { value: 'EXPIRED', label: 'منقضی‌شده' },
  { value: 'REVOKED', label: 'لغوشده' },
  { value: 'PENDING', label: 'در انتظار' }
];

/**
 * فایل‌های اشتراکی — ارسالی و دریافتی، با لغو/تمدید اشتراک.
 * به `/network/shares` متصل است؛ جهت از agency_idِ دفترِ جاری محاسبه می‌شود.
 */
export function SharedListingsView() {
  const auth = useAuthContext();
  const agencyId = auth.tenantId;
  const queryClient = useQueryClient();
  const [status, setStatus] = React.useState<ShareStatus | 'ALL'>('ALL');

  const outgoing = useShares({
    agencyId,
    direction: 'outgoing',
    status: status === 'ALL' ? undefined : status
  });
  const incoming = useShares({
    agencyId,
    direction: 'incoming',
    status: status === 'ALL' ? undefined : status
  });

  const revoke = useRevokeShare();
  const extend = useExtendShare();

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['network', 'shares'] });
  };

  const statusFilter = (
    <div className='flex flex-wrap gap-1.5'>
      {STATUS_FILTERS.map((f) => (
        <Button
          key={f.value}
          size='sm'
          variant={status === f.value ? 'default' : 'ghost'}
          onClick={() => setStatus(f.value)}
        >
          {f.label}
        </Button>
      ))}
    </div>
  );

  if (!agencyId) {
    return (
      <ListEmpty
        title='دفتر شما شناسایی نشد'
        description='برای دیدن فایل‌های اشتراکی، باید با حساب دفتر وارد شده باشید.'
      />
    );
  }

  return (
    <div className='space-y-5'>
      {statusFilter}
      <Tabs defaultValue='outgoing'>
        <TabsList>
          <TabsTrigger value='outgoing'>ارسالی‌های من</TabsTrigger>
          <TabsTrigger value='incoming'>دریافتی‌های من</TabsTrigger>
        </TabsList>

        <TabsContent value='outgoing' className='mt-4'>
          {outgoing.isPending ? (
            <ListSkeleton rows={4} />
          ) : outgoing.isError ? (
            <ListError onRetry={() => void outgoing.refetch()} />
          ) : (outgoing.data?.length ?? 0) === 0 ? (
            <ListEmpty title='اشتراک ارسالی ندارید' description='از صفحهٔ ملک یا فایل، آن را با دفتر همکار به اشتراک بگذارید.' />
          ) : (
            <div className='space-y-3'>
              {outgoing.data!.map((s) => (
                <ShareRow
                  key={s.id}
                  share={s}
                  canManage
                  onRevoke={() => revoke.mutate({ shareId: s.id }, { onSuccess: invalidate })}
                  onExtend={() => extend.mutate({ shareId: s.id, days: 30 }, { onSuccess: invalidate })}
                  pending={revoke.isPending || extend.isPending}
                />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value='incoming' className='mt-4'>
          {incoming.isPending ? (
            <ListSkeleton rows={4} />
          ) : incoming.isError ? (
            <ListError onRetry={() => void incoming.refetch()} />
          ) : (incoming.data?.length ?? 0) === 0 ? (
            <ListEmpty title='اشتراک دریافتی ندارید' description='وقتی دفتری فایلی را برای شما بفرستد، اینجا نمایش داده می‌شود.' />
          ) : (
            <div className='space-y-3'>
              {incoming.data!.map((s) => (
                <ShareRow key={s.id} share={s} />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ShareRow({
  share,
  canManage,
  onRevoke,
  onExtend,
  pending
}: {
  share: Share;
  canManage?: boolean;
  onRevoke?: () => void;
  onExtend?: () => void;
  pending?: boolean;
}) {
  const mode: ShareMode = share.mode;
  return (
    <Card>
      <CardContent className='flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between'>
        <div className='space-y-1.5'>
          <div className='flex flex-wrap items-center gap-2'>
            <span className='font-medium' dir='auto'>
              فایل {share.property_id.slice(0, 8)}…
            </span>
            <Badge variant='secondary'>{SHARE_MODE_LABELS[mode] ?? mode}</Badge>
            <ShareStatusBadge status={share.status} />
          </div>
          <p className='text-xs text-muted-foreground'>
            {share.target_agent ? `مسئول: ${share.target_agent} · ` : ''}
            ایجاد {formatJalali(share.created_at)}
            {share.expires_at ? ` · انقضا ${formatJalali(share.expires_at)}` : ' · بدون انقضا'}
          </p>
          {share.note ? <p className='text-xs text-muted-foreground'>«{share.note}»</p> : null}
          <div className='flex flex-wrap gap-1 pt-0.5'>
            <Badge variant='outline' className='gap-1 text-[10px]'>
              <IconEyeOff className='h-3 w-3' />
              شمارهٔ مالک پنهان
            </Badge>
            <Badge variant='outline' className='gap-1 text-[10px]'>
              <IconMapPin className='h-3 w-3' />
              آدرس دقیق پنهان
            </Badge>
          </div>
        </div>
        {canManage && (onRevoke || onExtend) ? (
          <div className='flex items-center gap-2'>
            {onExtend ? (
              <Button size='sm' variant='outline' disabled={pending} onClick={onExtend}>
                <IconRefresh className='ml-1 h-3.5 w-3.5' />
                تمدید ۳۰ روز
              </Button>
            ) : null}
            {onRevoke ? (
              <AlertDialog>
                <AlertDialogTrigger render={<Button size='sm' variant='destructive' disabled={pending} />}>
                  <IconTrash className='ml-1 h-3.5 w-3.5' />
                  لغو اشتراک
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>لغو اشتراک فایل؟</AlertDialogTitle>
                    <AlertDialogDescription>
                      دسترسی دفتر همکار بی‌درنگ بسته می‌شود و این عمل در لاگ امنیتی ثبت می‌گردد.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>انصراف</AlertDialogCancel>
                    <AlertDialogAction onClick={onRevoke}>لغو اشتراک</AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
