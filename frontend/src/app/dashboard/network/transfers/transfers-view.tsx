'use client';

import { useAuthContext } from '@/hooks/use-auth';
import { useTransfers } from '@/features/network/hooks';
import { TransferCreateDialog } from './transfer-create-dialog';
import {
  formatJalali,
  ListEmpty,
  ListError,
  ListSkeleton,
  TransferStatusBadge
} from '@/features/network/components/shared';

/**
 * تاریخچهٔ انتقال فایل — به `/network/transfers` متصل است.
 * هر سطر مسئولیت فایل را از یک دفتر به دفتر دیگر نشان می‌دهد.
 */
export function TransfersView() {
  const auth = useAuthContext();
  const agencyId = auth.tenantId;
  const transfers = useTransfers({ agencyId });

  if (!agencyId) {
    return <ListEmpty title='دفتر شما شناسایی نشد' description='برای دیدن تاریخچهٔ انتقال، باید با حساب دفتر وارد شده باشید.' />;
  }

  if (transfers.isPending) return <ListSkeleton rows={5} />;
  if (transfers.isError) return <ListError onRetry={() => void transfers.refetch()} />;
  if ((transfers.data?.length ?? 0) === 0) {
    return (
      <ListEmpty
        title='انتقالی ثبت نشده'
        description='انتقال فایل به دفتر دیگر، با تأیید صریح و ثبت در تاریخچه انجام می‌شود.'
      />
    );
  }

  return (
    <div className='space-y-3'>
      <div className='flex justify-end'>
        <TransferCreateDialog agencyId={agencyId} />
      </div>
      {transfers.data!.map((t) => (
        <div key={t.id} className='rounded-lg border border-border bg-card p-4'>
          <div className='flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between'>
            <div>
              <p className='font-medium' dir='auto'>
                فایل {t.property_id.slice(0, 8)}…
              </p>
              <p className='text-xs text-muted-foreground'>
                {t.from_user} → {t.to_user} · {formatJalali(t.created_at)}
              </p>
              {t.reason ? <p className='mt-1 text-xs text-muted-foreground'>دلیل: «{t.reason}»</p> : null}
              <p className='mt-1 text-xs text-muted-foreground'>
                کارمزد باقی‌ماندهٔ دفتر قبل: {t.residual_commission_pct}٪
              </p>
            </div>
            <TransferStatusBadge status={t.status} />
          </div>
        </div>
      ))}
    </div>
  );
}
