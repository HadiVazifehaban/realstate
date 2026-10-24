'use client';

import * as React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import PageContainer from '@/components/layout/page-container';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { fetchFinancialQueue, approveTestOrder, rejectOrder, receiptUrl, toman, type PaymentOrder } from '@/features/billing/api/client';
import { useRealmRoles } from '@/hooks/use-auth';

const reviewable = new Set(['receipt_submitted', 'under_review']);

export default function FinancialAdminPage() {
  const roles = useRealmRoles();
  const allowed = roles.includes('financial_admin') || roles.includes('ROLE_ADMIN');
  const [reasons, setReasons] = React.useState<Record<string, string>>({});
  const queryClient = useQueryClient();
  const queue = useQuery({ queryKey: ['billing', 'financial-queue'], queryFn: fetchFinancialQueue, enabled: allowed });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['billing', 'financial-queue'] });
  const approve = useMutation({ mutationFn: approveTestOrder, onSuccess: (order) => { toast.success(order.is_test ? 'تأیید آزمایشی ثبت شد؛ اشتراکی فعال نشد.' : 'پرداخت تأیید شد.'); void refresh(); }, onError: (error) => toast.error(error.message) });
  const reject = useMutation({ mutationFn: ({ id, reason }: { id: string; reason: string }) => rejectOrder(id, reason), onSuccess: () => { toast.success('درخواست رد شد.'); void refresh(); }, onError: (error) => toast.error(error.message) });

  return <PageContainer pageTitle='بررسی مالی' pageDescription='صف رسیدهای کارت‌به‌کارت و تاریخچه تصمیم مدیر مالی'>
    {!allowed ? <Alert variant='destructive' dir='rtl'><AlertDescription>دسترسی این صفحه فقط برای نقش مالی مجاز است.</AlertDescription></Alert> : <div className='space-y-4' dir='rtl'>
      {queue.data?.items.map((order: PaymentOrder) => <Card key={order.id}>
        <CardHeader><div className='flex flex-wrap items-center justify-between gap-2'><div><CardTitle>{order.order_number}</CardTitle><CardDescription>{toman(order.amount_toman)} تومان · پلن {order.plan}</CardDescription></div><div className='flex gap-2'><Badge>{order.status}</Badge><Badge variant={order.is_test ? 'destructive' : 'default'}>{order.is_test ? 'آزمایشی — وجه واریز نشود' : 'واقعی'}</Badge></div></div></CardHeader>
        <CardContent className='space-y-4'>
          {order.is_test && <Alert variant='destructive'><AlertDescription>این سفارش آزمایشی است. تأیید آن فقط وضعیت آزمایشی را ثبت می‌کند و اشتراک/تراکنش مالی واقعی ایجاد نمی‌کند.</AlertDescription></Alert>}
          {order.receipt && <div className='text-sm'>رسید: {order.receipt.original_filename} · پیگیری: {order.receipt.transfer_tracking_number} · {new Date(order.receipt.transfer_datetime).toLocaleString('fa-IR')}</div>}
          <div className='flex flex-wrap gap-2'>
            {order.receipt && <Button variant='outline' onClick={() => window.open(receiptUrl(order.id), '_blank', 'noopener,noreferrer')}>مشاهده امن رسید</Button>}
            {reviewable.has(order.status) && <>
              <Button disabled={approve.isPending} onClick={() => approve.mutate(order.id)}>{order.is_test ? 'تأیید آزمایشی بدون فعال‌سازی' : 'تأیید پرداخت واقعی'}</Button>
              <Input className='max-w-sm' placeholder='دلیل رد (الزامی)' value={reasons[order.id] ?? ''} onChange={(e) => setReasons((old) => ({ ...old, [order.id]: e.target.value }))} />
              <Button variant='destructive' disabled={!reasons[order.id]?.trim() || reject.isPending} onClick={() => reject.mutate({ id: order.id, reason: reasons[order.id] })}>رد درخواست</Button>
            </>}
          </div>
        </CardContent>
      </Card>)}
      {queue.isPending && <p>در حال دریافت صف مالی…</p>}
      {!queue.isPending && !queue.data?.items.length && <p className='text-muted-foreground'>درخواست بررسی‌نشده‌ای وجود ندارد.</p>}
    </div>}
  </PageContainer>;
}