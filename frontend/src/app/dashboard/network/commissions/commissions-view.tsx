'use client';

import * as React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { IconLock, IconReceipt, IconWallet } from '@tabler/icons-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
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

import { formatToman } from '@/lib/utils';
import { useAuthContext } from '@/hooks/use-auth';
import { useCommission, useCommissions, useLockCommission } from '@/features/network/hooks';
import {
  CommissionStatusBadge,
  formatJalali,
  ListEmpty,
  ListError,
  ListSkeleton
} from '@/features/network/components/shared';
import type { CommissionAgreement } from '@/features/network/types';

/**
 * دفتر کمیسیون — به `/network/commissions` متصل است.
 * سرجمع، جدول سهم‌ها و پرداخت‌ها و قفل کردن توافق.
 */
export function CommissionsView() {
  const auth = useAuthContext();
  const agencyId = auth.tenantId;
  const queryClient = useQueryClient();

  const commissions = useCommissions({ agencyId });
  const [openId, setOpenId] = React.useState<string | null>(null);

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['network', 'commissions'] });
  };

  if (!agencyId) {
    return (
      <ListEmpty
        title='دفتر شما شناسایی نشد'
        description='برای دیدن دفتر کمیسیون، باید با حساب دفتر وارد شده باشید.'
      />
    );
  }

  if (commissions.isPending) return <ListSkeleton rows={5} />;
  if (commissions.isError) return <ListError onRetry={() => void commissions.refetch()} />;

  const rows = commissions.data ?? [];
  const totalBasis = rows.reduce((s, r) => s + r.basis_amount, 0);
  const disputed = rows.filter((r) => r.status === 'DISPUTED').length;

  return (
    <div className='space-y-5'>
      <div className='grid gap-3 sm:grid-cols-3'>
        <SummaryCard icon={<IconReceipt className='h-4 w-4' />} label='تعداد توافق' value={String(rows.length)} />
        <SummaryCard icon={<IconWallet className='h-4 w-4' />} label='مجموع مبلغ پایه' value={formatToman(totalBasis)} />
        <SummaryCard icon={<IconLock className='h-4 w-4' />} label='مورد اختلاف' value={String(disputed)} />
      </div>

      {rows.length === 0 ? (
        <ListEmpty
          title='توافق کمیسیونی ثبت نشده'
          description='هنگام معاملهٔ مشترک بین دو دفتر، توافق کمیسیون اینجا ساخته می‌شود.'
        />
      ) : (
        <div className='space-y-3'>
          {rows.map((r) => (
            <CommissionRow key={r.id} r={r} onOpen={() => setOpenId(r.id)} />
          ))}
        </div>
      )}

      <CommissionDetailDialog agreementId={openId} onOpenChange={(v) => !v && setOpenId(null)} onLocked={invalidate} />
    </div>
  );
}

function SummaryCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <Card>
      <CardContent className='flex items-center gap-3 py-4'>
        <span className='text-primary'>{icon}</span>
        <div>
          <p className='text-xs text-muted-foreground'>{label}</p>
          <p className='text-lg font-semibold'>{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function CommissionRow({ r, onOpen }: { r: CommissionAgreement; onOpen: () => void }) {
  return (
    <Card>
      <CardContent className='flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between'>
        <div className='space-y-1'>
          <div className='flex flex-wrap items-center gap-2'>
            <span className='font-medium' dir='auto'>
              {r.property_id ? `ملک ${r.property_id.slice(0, 8)}…` : 'توافق بدون ملک'}
            </span>
            <Badge variant='secondary'>{r.model === 'PERCENTAGE' ? 'درصدی' : 'مبلغ ثابت'}</Badge>
            <CommissionStatusBadge status={r.status} />
          </div>
          <p className='text-xs text-muted-foreground'>
            مبلغ پایه {formatToman(r.basis_amount)} {r.currency} · {formatJalali(r.created_at)}
            {r.locked_at ? ` · قفل‌شده ${formatJalali(r.locked_at)}` : ''}
          </p>
        </div>
        <Button size='sm' variant='outline' onClick={onOpen}>
          جزئیات سهم‌ها و پرداخت‌ها
        </Button>
      </CardContent>
    </Card>
  );
}

function CommissionDetailDialog({
  agreementId,
  onOpenChange,
  onLocked
}: {
  agreementId: string | null;
  onOpenChange: (open: boolean) => void;
  onLocked: () => void;
}) {
  const detail = useCommission(agreementId);
  const lock = useLockCommission();
  const d = detail.data;
  const canLock = d && d.status === 'DRAFT';

  return (
    <Dialog open={!!agreementId} onOpenChange={onOpenChange}>
      <DialogContent className='sm:max-w-xl'>
        <DialogHeader>
          <DialogTitle>جزئیات توافق کمیسیون</DialogTitle>
          <DialogDescription>سهم‌ها، پرداخت‌ها و ماندهٔ باقی‌مانده.</DialogDescription>
        </DialogHeader>
        {detail.isPending ? (
          <ListSkeleton rows={3} />
        ) : detail.isError || !d ? (
          <ListError onRetry={() => void detail.refetch()} />
        ) : (
          <div className='space-y-4'>
            <div className='grid grid-cols-2 gap-2 text-sm'>
              <p className='text-muted-foreground'>مبلغ پایه: <span className='font-medium text-foreground'>{formatToman(d.basis_amount)}</span></p>
              <p className='text-muted-foreground'>پرداخت‌شده: <span className='font-medium text-foreground'>{formatToman(d.total_paid)}</span></p>
              <p className='text-muted-foreground'>باقی‌مانده: <span className='font-medium text-foreground'>{formatToman(d.remaining)}</span></p>
              <p className='text-muted-foreground'>وضعیت: <CommissionStatusBadge status={d.status} /></p>
            </div>

            <div>
              <h4 className='mb-2 text-sm font-medium'>سهم‌ها</h4>
              {d.allocations.length === 0 ? (
                <p className='text-xs text-muted-foreground'>سهمی ثبت نشده است.</p>
              ) : (
                <ul className='space-y-1'>
                  {d.allocations.map((a) => (
                    <li key={a.id} className='flex items-center justify-between rounded border border-border px-3 py-1.5 text-sm'>
                      <span dir='auto'>{a.agent || a.agency_id?.slice(0, 8) || '—'}</span>
                      <span className='text-muted-foreground'>
                        {d.model === 'PERCENTAGE' ? `${a.percent}٪` : formatToman(a.fixed_amount)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <h4 className='mb-2 text-sm font-medium'>پرداخت‌ها</h4>
              {d.payments.length === 0 ? (
                <p className='text-xs text-muted-foreground'>پرداختی ثبت نشده است.</p>
              ) : (
                <ul className='space-y-1'>
                  {d.payments.map((p) => (
                    <li key={p.id} className='flex items-center justify-between rounded border border-border px-3 py-1.5 text-sm'>
                      <span dir='auto'>{p.reference || 'بدون مرجع'} · {formatJalali(p.recorded_at)}</span>
                      <span className='text-muted-foreground'>{formatToman(p.amount)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {canLock ? (
              <div className='flex justify-end'>
                <AlertDialog>
                  <AlertDialogTrigger render={<Button size='sm' />}>
                    <IconLock className='ml-1 h-3.5 w-3.5' />
                    قفل کردن توافق
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>قفل کردن توافق کمیسیون؟</AlertDialogTitle>
                      <AlertDialogDescription>
                        پس از قفل، سهم‌ها دیگر قابل تغییر نیستند و برای ویرایش به تأیید مجدد نیاز است.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>انصراف</AlertDialogCancel>
                      <AlertDialogAction onClick={() => agreementId && lock.mutate({ agreementId }, { onSuccess: onLocked })}>
                        قفل کن
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            ) : null}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
