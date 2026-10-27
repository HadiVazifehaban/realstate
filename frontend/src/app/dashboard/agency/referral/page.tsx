'use client';

import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import PageContainer from '@/components/layout/page-container';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { fetchReferralSummary } from '@/features/billing/api/client';
import { toast } from 'sonner';
import { useAuthContext } from '@/hooks/use-auth';
import Link from 'next/link';

const percent = (value: number | undefined) => `${value ?? 0}٪`;

export default function AgencyReferralPage() {
  const { roles } = useAuthContext();
  const allowed = roles.some((role) => ['ROLE_ADMIN', 'ROLE_AGENCY_MANAGER'].includes(role));
  const query = useQuery({ queryKey: ['agency-referral'], queryFn: fetchReferralSummary, enabled: allowed });
  const referralUrl = typeof window !== 'undefined' && query.data
    ? new URL('/auth/sign-up', window.location.origin)
    : null;

  async function copy(text: string, message: string) {
    try { await navigator.clipboard.writeText(text); toast.success(message); }
    catch { toast.error('کپی انجام نشد؛ متن را دستی انتخاب کنید.'); }
  }

  return <PageContainer pageTitle='دعوت از همکاران و تخفیف‌ها' pageDescription='کد معرف دفتر و سهمیه‌های تخفیف تمدید'>
    <div className='space-y-5' dir='rtl'>
      {!allowed && <Alert><AlertDescription>نمایش کد معرف فقط برای مدیر دفتر مجاز است.</AlertDescription></Alert>}
      {query.isError && <Alert variant='destructive'><AlertDescription>{(query.error as Error).message}</AlertDescription></Alert>}
      {query.isPending && allowed && <p>در حال دریافت اطلاعات…</p>}
      {query.data && <>
        <Card><CardHeader><CardTitle>کد معرف اختصاصی دفتر</CardTitle><CardDescription>با دعوت از دفتر همکار، پس از اولین پرداخت موفق اشتراک پولی، یک سهمیهٔ ۵٪ برای تمدید شما ایجاد می‌شود.</CardDescription></CardHeader>
          <CardContent className='flex flex-wrap items-center gap-3'>
            <code className='rounded-md border px-4 py-2 text-lg font-bold tracking-wider'>{query.data.referral_code}</code>
            <Button variant='outline' onClick={() => void copy(query.data!.referral_code, 'کد معرف کپی شد.')}>کپی کد</Button>
            {referralUrl && <Button variant='outline' onClick={() => void copy(referralUrl.toString(), 'لینک دعوت کپی شد.')}>کپی لینک دعوت</Button>}
            {typeof navigator !== 'undefined' && navigator.share && referralUrl && <Button onClick={() => void navigator.share({ title: 'دعوت به شکارچی', url: referralUrl.toString() })}>اشتراک‌گذاری</Button>}
            <Button variant='outline' render={<Link href='/dashboard/network/agencies' />}>ثبت دفتر با کد معرف</Button>
          </CardContent>
        </Card>
        <section className='grid gap-3 sm:grid-cols-2 lg:grid-cols-4'>
          <Card><CardHeader><CardTitle>معرفی در انتظار</CardTitle></CardHeader><CardContent>{query.data.pending_referrals}</CardContent></Card>
          <Card><CardHeader><CardTitle>معرفی تکمیل‌شده</CardTitle></CardHeader><CardContent>{query.data.completed_referrals}</CardContent></Card>
          <Card><CardHeader><CardTitle>سهمیه قابل استفاده</CardTitle></CardHeader><CardContent>{percent(query.data.credits.available)} · سقف هر تمدید {percent(query.data.policy.invoice_cap_percent)}</CardContent></Card>
          <Card><CardHeader><CardTitle>تمدید بعدی</CardTitle></CardHeader><CardContent>سهمیه قابل استفاده در تمدید بعدی: {percent(query.data.next_renewal_percent)} از سقف {percent(query.data.policy.invoice_cap_percent)}</CardContent></Card>
        </section>
        <Card><CardHeader><CardTitle>دفترکل سهمیه‌ها</CardTitle><CardDescription>سهمیهٔ ایجادشده پس از تأیید واقعی اولین پرداخت دفتر معرفی‌شده، از طریق بررسی کارت‌به‌کارت.</CardDescription></CardHeader><CardContent className='grid gap-2 text-sm sm:grid-cols-3'>
          <p>در انتظار: {percent(query.data.credits.pending)}</p><p>رزروشده: {percent(query.data.credits.reserved)}</p><p>مصرف‌شده: {percent(query.data.credits.consumed)}</p><p>آزادشده: {percent(query.data.credits.released)}</p><p>باطل‌شده: {percent(query.data.credits.voided)}</p>
        </CardContent></Card>
        <Card><CardHeader><CardTitle>تاریخچه معرفی‌ها</CardTitle><CardDescription>برای رعایت حریم خصوصی، مشخصات دفترهای دعوت‌شده در این فهرست نمایش داده نمی‌شود.</CardDescription></CardHeader><CardContent className='space-y-2'>
          {query.data.referrals.map((item, index) => <div key={`${item.created_at}-${index}`} className='flex flex-wrap justify-between gap-2 rounded border p-3 text-sm'>
            <span>{item.status === 'COMPLETED' ? 'تکمیل‌شده' : item.status === 'PENDING' ? 'در انتظار خرید اشتراک پولی' : 'باطل‌شده'}</span>
            <span>ثبت: {new Date(item.created_at).toLocaleDateString('fa-IR')}</span>
            {item.completed_at && <span>تکمیل: {new Date(item.completed_at).toLocaleDateString('fa-IR')}</span>}
          </div>)}
          {!query.data.referrals.length && <p className='text-sm text-muted-foreground'>هنوز معرفی‌ای ثبت نشده است.</p>}
        </CardContent></Card>
      </>}
    </div>
  </PageContainer>;
}