'use client';

import * as React from 'react';
import { IconShieldLock } from '@tabler/icons-react';

import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';

import { useAudit } from '@/features/network/hooks';
import { formatJalaliDateTime, ListEmpty, ListError, ListSkeleton } from '@/features/network/components/shared';
import { AUDIT_ACTION_LABELS, type AuditAction } from '@/features/network/types';

const ACTION_FILTERS: { value: AuditAction | 'ALL'; label: string }[] = [
  { value: 'ALL', label: 'همهٔ عملیات' },
  { value: 'OWNER_PHONE_REVEALED', label: 'افشای شمارهٔ مالک' },
  { value: 'ADDRESS_REVEALED', label: 'افشای آدرس دقیق' },
  { value: 'LISTING_EXPORTED', label: 'خروجی گرفتن' },
  { value: 'PERMISSION_CHANGED', label: 'تغییر دسترسی' },
  { value: 'SHARE_CREATED', label: 'ایجاد اشتراک' },
  { value: 'SHARE_REVOKED', label: 'لغو اشتراک' },
  { value: 'TRANSFER_EXECUTED', label: 'انتقال فایل' },
  { value: 'COMMISSION_LOCKED', label: 'قفل پورسانت' },
  { value: 'PAYMENT_RECORDED', label: 'ثبت پرداخت' },
  { value: 'DISPUTE_OPENED', label: 'ثبت اختلاف' }
];

/**
 * لاگ امنیتی شبکه — به `/network/audit` متصل است.
 * هر رویداد حساس (افشا، خروجی، تغییر دسترسی، لغو، انتقال، مالی) اینجا ثبت می‌شود.
 */
export function AuditView() {
  const [action, setAction] = React.useState<AuditAction | 'ALL'>('ALL');
  const audit = useAudit({ action: action === 'ALL' ? undefined : action, limit: 200 });

  if (audit.isPending) return <ListSkeleton rows={8} />;
  if (audit.isError) return <ListError onRetry={() => void audit.refetch()} />;
  if ((audit.data?.length ?? 0) === 0) {
    return (
      <ListEmpty
        title='رویدادی ثبت نشده'
        description='به‌محض انجام عملیات حساس روی اشتراک، دسترسی یا مالی، اینجا ثبت می‌شود.'
      />
    );
  }

  return (
    <div className='space-y-4'>
      <div className='flex items-center gap-2'>
        <Select value={action} onValueChange={(v) => setAction((v ?? 'ALL') as AuditAction | 'ALL')}>
          <SelectTrigger className='w-56' aria-label='فیلتر عملیات'>
            <SelectValue placeholder='عملیات' />
          </SelectTrigger>
          <SelectContent>
            {ACTION_FILTERS.map((f) => (
              <SelectItem key={f.value} value={f.value}>
                {f.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className='text-xs text-muted-foreground'>{audit.data!.length} رویداد</span>
      </div>

      <ul className='divide-y divide-border rounded-lg border border-border'>
        {audit.data!.map((e) => (
          <li key={e.id} className='flex items-start gap-3 px-4 py-3'>
            <IconShieldLock className='mt-0.5 h-4 w-4 shrink-0 text-primary' />
            <div className='min-w-0 flex-1'>
              <div className='flex flex-wrap items-center gap-2'>
                <span className='text-sm font-medium' dir='auto'>
                  {AUDIT_ACTION_LABELS[e.action] ?? e.action}
                </span>
                <Badge variant='outline' className='text-[10px]'>
                  {e.entity_type}
                </Badge>
              </div>
              <p className='mt-0.5 truncate text-xs text-muted-foreground' dir='auto'>
                {e.detail}
              </p>
              <p className='mt-0.5 text-[11px] text-muted-foreground'>
                {e.actor} · {formatJalaliDateTime(e.created_at)}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
