'use client';

import * as React from 'react';
import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import PageContainer from '@/components/layout/page-container';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { fetchOrders, fetchPlans, fetchSubscription, createOrder, submitReceipt, toman, groupedCard, type PaymentOrder } from '@/features/billing/api/client';

const STATUS: Record<string, string> = {
  created: 'ایجادشده', awaiting_transfer: 'در انتظار انتقال', receipt_submitted: 'رسید ثبت‌شده',
  under_review: 'در حال بررسی', test_approved_no_activation: 'تأیید آزمایشی — بدون فعال‌سازی',
  approved: 'تأیید و فعال‌شده', rejected: 'ردشده', expired: 'منقضی', cancelled: 'لغوشده'
};

export default function BillingPage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = React.useState<PaymentOrder | null>(null);
  const [receiptFile, setReceiptFile] = React.useState<File | null>(null);
  const [tracking, setTracking] = React.useState('');
  const [transferAt, setTransferAt] = React.useState('');
  const plans = useQuery({ queryKey: ['billing', 'plans'], queryFn: fetchPlans });
  const orders = useQuery({ queryKey: ['billing', 'orders'], queryFn: fetchOrders });
  const subscription = useQuery({ queryKey: ['billing', 'subscription'], queryFn: fetchSubscription });
  const create = useMutation({ mutationFn: createOrder, onSuccess: (order) => {
    setSelected(order); void queryClient.invalidateQueries({ queryKey: ['billing'] });
  }, onError: (error) => toast.error(error.message) });
  const upload = useMutation({ mutationFn: () => {
    if (!selected || !receiptFile) throw new Error('رسید را انتخاب کنید.');
    return submitReceipt(selected.id, { file: receiptFile, trackingNumber: tracking, transferDateTime: new Date(transferAt).toISOString() });
  }, onSuccess: (result) => {
    toast.success(result.message); setSelected(null); setReceiptFile(null); setTracking(''); setTransferAt('');
    void queryClient.invalidateQueries({ queryKey: ['billing'] });
  }, onError: (error) => toast.error(error.message) });

  async function copyCard() {
    if (!selected?.card_number) return;
    try { await navigator.clipboard.writeText(groupedCard(selected.card_number)); toast.success('شماره کارت کپی شد.'); }
    catch { toast.error('کپی شماره کارت ممکن نشد.'); }
  }

  return <PageContainer pageTitle='اشتراک و پرداخت' pageDescription='خرید اشتراک از طریق کارت‌به‌کارت و بررسی دستی مدیر مالی'>
    <div className='space-y-6' dir='rtl'>
      {subscription.data && <Card><CardHeader><CardTitle>وضعیت اشتراک</CardTitle><CardDescription>اطلاعات از حساب کاربری شما دریافت شده است.</CardDescription></CardHeader>
        <CardContent className='flex flex-wrap items-center gap-4 text-sm'>
          <Badge>{subscription.data.title}</Badge>
          <span>سهمیه آگهی: {subscription.data.is_unlimited ? 'نامحدود' : subscription.data.listing_quota ?? '—'}</span>
          <span>رادار لید: {subscription.data.sms_quota}</span>
          {subscription.data.expires_at && <span>انقضا: {new Date(subscription.data.expires_at).toLocaleDateString('fa-IR')}</span>}
        </CardContent></Card>}

      {selected && <Card className='border-[#c88252]/50'><CardHeader><CardTitle>دستور پرداخت — {selected.order_number}</CardTitle>
        <CardDescription>مبلغ سفارش: {toman(selected.amount_toman)} تومان</CardDescription></CardHeader>
        <CardContent className='space-y-5'>
          {selected.is_test && <Alert variant='destructive'><AlertDescription>شماره کارت فعلاً آزمایشی است. لطفاً وجهی واریز نکنید. شماره کارت صفرها کارت معتبر بانکی نیست.</AlertDescription></Alert>}
          {!selected.is_test && selected.card_number && <div className='flex flex-wrap items-center gap-3 rounded-xl border p-4'>
            <span className='font-mono text-lg tracking-widest' dir='ltr'>{groupedCard(selected.card_number)}</span>
            <Button type='button' variant='outline' onClick={copyCard}>کپی شماره کارت</Button>
            <span>{selected.card_holder}</span>
          </div>}
          <p className='text-sm text-muted-foreground'>پس از انتقال، تصویر رسید، شماره پیگیری و زمان انتقال را وارد کنید. بارگذاری رسید به‌معنای تأیید پرداخت یا فعال‌شدن اشتراک نیست.</p>
          <div className='grid gap-4 md:grid-cols-3'>
            <div className='space-y-2'><Label htmlFor='receipt'>رسید (JPEG، PNG، WebP یا PDF)</Label><Input id='receipt' type='file' accept='image/jpeg,image/png,image/webp,application/pdf' onChange={(event) => setReceiptFile(event.target.files?.[0] ?? null)} /></div>
            <div className='space-y-2'><Label htmlFor='tracking'>شماره پیگیری</Label><Input id='tracking' value={tracking} onChange={(e) => setTracking(e.target.value)} maxLength={128} /></div>
            <div className='space-y-2'><Label htmlFor='transfer-at'>زمان انتقال</Label><Input id='transfer-at' type='datetime-local' value={transferAt} onChange={(e) => setTransferAt(e.target.value)} /></div>
          </div>
          <div className='flex gap-2'><Button disabled={!receiptFile || !tracking || !transferAt || upload.isPending} onClick={() => upload.mutate()}>{upload.isPending ? 'در حال ارسال…' : 'ارسال برای بررسی مالی'}</Button><Button variant='outline' onClick={() => setSelected(null)}>بستن</Button></div>
        </CardContent></Card>}

      <section className='grid gap-4 md:grid-cols-2 xl:grid-cols-4'>
        {plans.data?.plans.map((plan) => <Card key={plan.id} className='flex flex-col border-border/70 bg-card/80 backdrop-blur'>
          <CardHeader><CardTitle>{plan.title}</CardTitle><CardDescription>{plan.duration_days} روز</CardDescription></CardHeader>
          <CardContent className='flex flex-1 flex-col gap-4'>
            <p className='text-2xl font-bold text-[#e5a87b]'>{plan.price_toman === 0 ? 'رایگان' : `${toman(plan.price_toman)} تومان`}</p>
            <ul className='space-y-2 text-sm text-muted-foreground'>
              <li>آگهی: {plan.is_unlimited ? 'نامحدود طبق سیاست استفاده منصفانه' : plan.listing_quota}</li>
              <li>پیامک رادار لید: {plan.sms_quota}</li><li>مناطق فایلینگ: {plan.regions_quota || '—'}</li>
              <li>مشاور: {plan.advisor_quota ?? 'نامحدود طبق استفاده منصفانه'}</li>
              {plan.features.map((feature) => <li key={feature}>{feature}</li>)}
            </ul>
            {plan.id !== 'free' && <Button className='mt-auto' disabled={create.isPending} onClick={() => create.mutate(plan.id)}>ایجاد سفارش کارت‌به‌کارت</Button>}
          </CardContent>
        </Card>)}
      </section>

      <Card><CardHeader><CardTitle>تاریخچه پرداخت‌ها</CardTitle><CardDescription>وضعیت سفارش‌ها و رسیدهای ارسالی</CardDescription></CardHeader>
        <CardContent className='space-y-3'>
          {orders.isPending && <p>در حال دریافت…</p>}
          {orders.data?.items.map((order) => <div key={order.id} className='flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3'>
            <div><p className='font-medium'>{order.order_number} · {toman(order.amount_toman)} تومان</p><p className='text-sm text-muted-foreground'>{new Date(order.created_at).toLocaleString('fa-IR')}</p></div>
            <div className='flex items-center gap-2'><Badge variant={order.is_test ? 'outline' : 'default'}>{order.is_test ? 'آزمایشی' : 'واقعی'}</Badge><Badge variant='secondary'>{STATUS[order.status] ?? order.status}</Badge>
              {order.status === 'awaiting_transfer' && <Button variant='outline' size='sm' onClick={() => setSelected(order)}>ثبت رسید</Button>}
            </div>
          </div>)}
          {!orders.isPending && !orders.data?.items.length && <p className='text-sm text-muted-foreground'>هنوز سفارشی ثبت نشده است.</p>}
          <Link className='text-sm text-[#c88252] underline' href='/dashboard/billing/financial'>ورود به پنل بررسی مالی</Link>
        </CardContent></Card>
    </div>
  </PageContainer>;
}