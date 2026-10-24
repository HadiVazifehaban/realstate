'use client';

import Link from 'next/link';
import {
  IconBuilding,
  IconChartBar,
  IconGavel,
  IconBriefcase,
  IconRepeat,
  IconShare2,
  IconShieldLock,
  IconUsers,
  IconWallet,
} from '@tabler/icons-react';

import { Card, CardContent } from '@/components/ui/card';
import { formatToman } from '@/lib/utils';
import { useAuthContext } from '@/hooks/use-auth';
import { useNetworkOverview } from '@/features/network/hooks';
import { ListError, ListSkeleton } from '@/features/network/components/shared';

const MENUS = [
  { href: '/dashboard/network/agencies', title: 'دفاتر همکار', desc: 'فهرست و جستجوی دفاتر شبکه', icon: IconBuilding, key: 'agencies_total' },
  { href: '/dashboard/network/requests', title: 'درخواست‌های همکاری', desc: 'ارسالی و دریافتی با تأیید و رد', icon: IconBriefcase, key: 'cooperations_pending' },
  { href: '/dashboard/network/shared-listings', title: 'فایل‌های اشتراکی', desc: 'اشتراک ارسالی و دریافتی با لغو و تمدید', icon: IconShare2, key: 'shares_active' },
  { href: '/dashboard/network/referrals', title: 'ارجاع‌ها', desc: 'ارجاع مشتری با پیگیری مرحله', icon: IconUsers, key: 'referrals_open' },
  { href: '/dashboard/network/transfers', title: 'انتقال فایل‌ها', desc: 'تاریخچه انتقال مسئولیت فایل', icon: IconRepeat, key: 'transfers_total' },
  { href: '/dashboard/network/commissions', title: 'کمیسیون و تسویه', desc: 'توافق، سهم، پرداخت و قفل', icon: IconWallet, key: 'commissions_open' },
  { href: '/dashboard/network/disputes', title: 'اختلافات', desc: 'ثبت و پیگیری اختلاف بین دفاتر', icon: IconGavel, key: 'disputes_open' },
  { href: '/dashboard/network/reports', title: 'گزارش همکاری‌ها', desc: 'شاخص‌ها و روند همکاری', icon: IconChartBar, key: 'conversion' },
  { href: '/dashboard/network/audit', title: 'رهگیری و لاگ', desc: 'لاگ امنیتی عملیات حساس', icon: IconShieldLock, key: 'audit_total' },
] as const;

/** داشبورد شبکه: کارت هر منو + سرجمع زنده از API. */
export function NetworkDashboard() {
  const auth = useAuthContext();
  const overview = useNetworkOverview({ agencyId: auth.tenantId ?? undefined });

  if (overview.isPending) return <ListSkeleton rows={6} />;
  if (overview.isError) return <ListError onRetry={() => void overview.refetch()} />;

  const o = overview.data!;
  const values: Record<string, string> = {
    agencies_total: `${o.agencies_total} دفتر (${o.agencies_verified} تأییدشده)`,
    cooperations_pending: `${o.cooperations_pending} در انتظار · ${o.cooperations_approved} فعال`,
    shares_active: `${o.shares_active} فعال از ${o.shares_total}`,
    referrals_open: `${o.referrals_open} باز · ${o.referrals_converted} تبدیل‌شده`,
    transfers_total: `${o.transfers_total} انتقال`,
    commissions_open: `${o.commissions_open} باز · ${formatToman(o.commissions_basis_total)}`,
    disputes_open: `${o.disputes_open} باز`,
    conversion: `نرخ تبدیل ارجاع: ${o.referrals_open + o.referrals_converted > 0 ? Math.round((o.referrals_converted * 100) / Math.max(o.referrals_open + o.referrals_converted, 1)) : 0}٪`,
    audit_total: `${o.audit_total} رویداد`,
  };

  return (
    <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
      {MENUS.map((m) => (
        <Link key={m.href} href={m.href}>
          <Card className='h-full transition-colors hover:border-primary/40'>
            <CardContent className='flex items-start gap-3 py-4'>
              <span className='rounded-md bg-primary/10 p-2 text-primary'>
                <m.icon className='h-5 w-5' />
              </span>
              <span>
                <span className='block font-medium'>{m.title}</span>
                <span className='mt-0.5 block text-xs text-muted-foreground'>{m.desc}</span>
                <span className='mt-1.5 block text-xs font-medium text-primary'>{values[m.key]}</span>
              </span>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  );
}
