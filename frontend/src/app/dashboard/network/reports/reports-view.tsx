'use client';

import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatToman } from '@/lib/utils';
import { useAuthContext } from '@/hooks/use-auth';
import { useNetworkReports } from '@/features/network/hooks';
import { ListEmpty, ListError, ListSkeleton } from '@/features/network/components/shared';
import type { ReportsByStatus } from '@/features/network/types';

const COLORS = ['#2563eb', '#16a34a', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#64748b'];

/** گزارش‌های همکاری: توزیع وضعیت هر منو + سرجمع مالی. */
export function ReportsView() {
  const auth = useAuthContext();
  const reports = useNetworkReports({ agencyId: auth.tenantId ?? undefined });

  if (reports.isPending) return <ListSkeleton rows={6} />;
  if (reports.isError) return <ListError onRetry={() => void reports.refetch()} />;
  const r = reports.data!;
  const empty = [r.shares_by_status, r.referrals_by_stage, r.transfers_by_status, r.commissions_by_status, r.disputes_by_status, r.cooperations_by_status].every((a) => a.length === 0);
  if (empty) {
    return <ListEmpty title='داده‌ای برای گزارش نیست' description='با ثبت دفتر، اشتراک، ارجاع و کمیسیون، نمودارها اینجا ساخته می‌شوند.' />;
  }

  return (
    <div className='space-y-5'>
      <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-4'>
        <SummaryCard label='مبلغ پایه کمیسیون' value={formatToman(r.total_basis)} />
        <SummaryCard label='پرداخت‌شده' value={formatToman(r.total_paid)} />
        <SummaryCard label='باقی‌مانده' value={formatToman(r.total_remaining)} />
        <SummaryCard label='نرخ تبدیل ارجاع' value={`${r.conversion_rate_pct}٪`} />
      </div>
      <div className='grid gap-4 lg:grid-cols-2'>
        <DistCard title='فایل‌های اشتراکی برحسب وضعیت' data={r.shares_by_status} />
        <DistCard title='ارجاع‌ها برحسب مرحله' data={r.referrals_by_stage} />
        <DistCard title='انتقال‌ها برحسب وضعیت' data={r.transfers_by_status} />
        <DistCard title='کمیسیون‌ها برحسب وضعیت' data={r.commissions_by_status} />
        <DistCard title='اختلافات برحسب وضعیت' data={r.disputes_by_status} />
        <DistCard title='همکاری‌ها برحسب وضعیت' data={r.cooperations_by_status} />
      </div>
      {r.audit_by_action.length > 0 ? (
        <Card>
          <CardHeader className='pb-2'><CardTitle className='text-sm'>رویدادهای امنیتی برحسب نوع</CardTitle></CardHeader>
          <CardContent className='h-64' dir='ltr'>
            <ResponsiveContainer width='100%' height='100%'>
              <BarChart data={r.audit_by_action.map((a) => ({ name: a.label_fa || a.status, count: a.count }))}>
                <CartesianGrid strokeDasharray='3 3' />
                <XAxis dataKey='name' tick={{ fontSize: 10 }} interval={0} angle={-20} height={60} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey='count' fill='#2563eb' radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className='py-4'>
        <p className='text-xs text-muted-foreground'>{label}</p>
        <p className='mt-1 text-lg font-semibold'>{value}</p>
      </CardContent>
    </Card>
  );
}

function DistCard({ title, data }: { title: string; data: ReportsByStatus[] }) {
  if (data.length === 0) return null;
  return (
    <Card>
      <CardHeader className='pb-2'><CardTitle className='text-sm'>{title}</CardTitle></CardHeader>
      <CardContent className='h-60' dir='ltr'>
        <ResponsiveContainer width='100%' height='100%'>
          <PieChart>
            <Pie data={data} dataKey='count' nameKey='label_fa' innerRadius={45} outerRadius={75} paddingAngle={2}>
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
        <ul className='mt-1 space-y-1' dir='rtl'>
          {data.map((d, i) => (
            <li key={d.status} className='flex items-center justify-between text-xs'>
              <span><span className='ml-1 inline-block h-2 w-2 rounded-full' style={{ background: COLORS[i % COLORS.length] }} />{d.label_fa || d.status}</span>
              <span className='text-muted-foreground'>{d.count}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
