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
import {
  fetchFinancialQueue,
  fetchFinancialAttempts,
  fetchFinancialAuditLogs,
  approveTestOrder,
  rejectOrder,
  reconcilePaymentAttempt,
  confirmZibalAttemptNotPaid,
  runFinancialReconciliation,
  fetchManagedPlans,
  createManagedPlan,
  updateManagedPlan,
  receiptUrl,
  toman,
  type ManagedBillingPlan,
  type PlanFields,
  type PaymentOrder
} from '@/features/billing/api/client';
import { useRealmRoles } from '@/hooks/use-auth';

const reviewable = new Set(['receipt_submitted', 'under_review']);
type PlanFormState = {
  id: string;
  title: string;
  description: string;
  price_toman: string;
  duration_days: string;
  listing_quota: string;
  sms_quota: string;
  regions_quota: string;
  advisor_quota: string;
  is_unlimited: boolean;
  features: string;
  is_active: boolean;
  sort_order: string;
};

const emptyPlan: PlanFormState = {
  id: '', title: '', description: '', price_toman: '', duration_days: '', listing_quota: '3',
  sms_quota: '0', regions_quota: '0', advisor_quota: '1', is_unlimited: false,
  features: '', is_active: true, sort_order: '10'
};

export default function FinancialAdminPage() {
  const roles = useRealmRoles();
  const allowed = roles.includes('financial_admin') || roles.includes('ROLE_ADMIN');
  const [reasons, setReasons] = React.useState<Record<string, string>>({});
  const [status, setStatus] = React.useState('');
  const [isTest, setIsTest] = React.useState('');
  const [search, setSearch] = React.useState('');
  const [page, setPage] = React.useState(1);
  const [unpaidReasons, setUnpaidReasons] = React.useState<Record<string, string>>({});
  const [planForm, setPlanForm] = React.useState<PlanFormState>(emptyPlan);
  const [editingPlan, setEditingPlan] = React.useState<string | null>(null);
  const queryClient = useQueryClient();
  const queueOptions = { page, status: status || undefined, isTest: isTest === '' ? undefined : isTest === 'true', q: search || undefined };
  const queue = useQuery({ queryKey: ['billing', 'financial-queue', queueOptions], queryFn: () => fetchFinancialQueue(queueOptions), enabled: allowed });
  const attempts = useQuery({ queryKey: ['billing', 'financial-reconciliation'], queryFn: () => fetchFinancialAttempts({ reconciliationOnly: true }), enabled: allowed });
  const audits = useQuery({ queryKey: ['billing', 'financial-audit'], queryFn: () => fetchFinancialAuditLogs({ page: 1 }), enabled: allowed });
  const plans = useQuery({ queryKey: ['billing', 'admin-plans'], queryFn: fetchManagedPlans, enabled: allowed });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['billing'] });
  const approve = useMutation({ mutationFn: approveTestOrder, onSuccess: (order) => { toast.success(order.is_test ? 'تأیید آزمایشی ثبت شد؛ اشتراکی فعال نشد.' : 'پرداخت تأیید شد.'); void refresh(); }, onError: (error) => toast.error(error.message) });
  const reject = useMutation({ mutationFn: ({ id, reason }: { id: string; reason: string }) => rejectOrder(id, reason), onSuccess: () => { toast.success('درخواست رد شد.'); void refresh(); }, onError: (error) => toast.error(error.message) });
  const reconcile = useMutation({
    mutationFn: reconcilePaymentAttempt,
    onSuccess: (result) => { toast.success(result.result === 'success' ? 'پرداخت با استعلام زیبال تأیید شد.' : 'وضعیت تراکنش به‌روزرسانی شد.'); void refresh(); },
    onError: (error) => toast.error(error.message)
  });
  const reconcileBatch = useMutation({
    mutationFn: runFinancialReconciliation,
    onSuccess: (result) => { toast.success(`استعلام انجام شد؛ ${result.paid} پرداخت قطعی شد.`); void refresh(); },
    onError: (error) => toast.error(error.message)
  });
  const confirmNotPaid = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => confirmZibalAttemptNotPaid(id, reason),
    onSuccess: () => { toast.success('سفارش برای جلوگیری از پرداخت تکراری لغو و دلیل ممیزی شد.'); void refresh(); },
    onError: (error) => toast.error(error.message)
  });
  const planMutation = useMutation({
    mutationFn: () => {
      const payload: PlanFields = {
        title: planForm.title.trim(), description: planForm.description.trim(),
        price_toman: Number(planForm.price_toman), duration_days: Number(planForm.duration_days),
        listing_quota: planForm.is_unlimited ? null : Number(planForm.listing_quota),
        sms_quota: Number(planForm.sms_quota), regions_quota: Number(planForm.regions_quota),
        advisor_quota: planForm.is_unlimited ? null : Number(planForm.advisor_quota),
        is_unlimited: planForm.is_unlimited,
        features: planForm.features.split('\n').map((value) => value.trim()).filter(Boolean),
        is_active: planForm.is_active, sort_order: Number(planForm.sort_order)
      };
      return editingPlan ? updateManagedPlan(editingPlan, payload) : createManagedPlan({ ...payload, id: planForm.id.trim() });
    },
    onSuccess: async () => {
      toast.success(editingPlan ? 'پلن به‌روزرسانی شد؛ فاکتورهای قبلی Snapshot خود را حفظ می‌کنند.' : 'پلن جدید ایجاد شد.');
      setPlanForm(emptyPlan);
      setEditingPlan(null);
      await queryClient.invalidateQueries({ queryKey: ['billing', 'admin-plans'] });
      await queryClient.invalidateQueries({ queryKey: ['billing', 'plans'] });
    },
    onError: (error) => toast.error(error.message)
  });

  const editPlan = (plan: ManagedBillingPlan) => {
    setEditingPlan(plan.id);
    setPlanForm({
      id: plan.id, title: plan.title, description: plan.description, price_toman: String(plan.price_toman),
      duration_days: String(plan.duration_days), listing_quota: plan.listing_quota == null ? '' : String(plan.listing_quota),
      sms_quota: String(plan.sms_quota), regions_quota: String(plan.regions_quota),
      advisor_quota: plan.advisor_quota == null ? '' : String(plan.advisor_quota),
      is_unlimited: plan.is_unlimited, features: plan.features.join('\n'),
      is_active: plan.is_active, sort_order: String(plan.sort_order)
    });
  };

  return <PageContainer pageTitle='بررسی مالی' pageDescription='صف رسیدها، تراکنش‌های زیبال و رویدادهای ممیزی'>
    {!allowed ? <Alert variant='destructive' dir='rtl'><AlertDescription>دسترسی این صفحه فقط برای نقش مالی مجاز است.</AlertDescription></Alert> : <div className='space-y-4' dir='rtl'>
      <Card>
        <CardHeader><CardTitle>کاتالوگ پلن‌های اشتراک</CardTitle><CardDescription>قیمت و شرایط جدید فقط روی سفارش‌های بعدی اعمال می‌شوند؛ فاکتورها Snapshot زمان صدور را نگه می‌دارند.</CardDescription></CardHeader>
        <CardContent className='space-y-4'>
          <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-4'>
            {plans.data?.items.map((plan) => <div key={plan.id} className='flex flex-col justify-between gap-2 rounded-lg border p-3'>
              <div><div className='font-medium'>{plan.title}</div><div className='text-xs text-muted-foreground'>{plan.id} · {toman(plan.price_toman)} تومان · {plan.duration_days} روز · {plan.is_active ? 'فعال' : 'غیرفعال'}</div><div className='mt-1 text-xs text-muted-foreground'>{plan.is_unlimited ? 'آگهی/مشاور نامحدود' : `${plan.listing_quota} آگهی · ${plan.advisor_quota} مشاور`} · {plan.sms_quota} پیامک · {plan.regions_quota} منطقه</div></div>
              <Button size='sm' variant='outline' onClick={() => editPlan(plan)}>ویرایش پلن</Button>
            </div>)}
          </div>
          <div className='grid gap-3 border-t pt-4 sm:grid-cols-2 lg:grid-cols-4'>
            {!editingPlan && <Input aria-label='شناسه پلن' placeholder='شناسه (مثلاً silver_6m)' value={planForm.id} onChange={(event) => setPlanForm((value) => ({ ...value, id: event.target.value }))} />}
            <Input aria-label='نام پلن' placeholder='عنوان پلن' value={planForm.title} onChange={(event) => setPlanForm((value) => ({ ...value, title: event.target.value }))} />
            <Input aria-label='قیمت پلن به تومان' type='number' min={0} placeholder='قیمت تومان' value={planForm.price_toman} onChange={(event) => setPlanForm((value) => ({ ...value, price_toman: event.target.value }))} />
            <Input aria-label='مدت پلن به روز' type='number' min={0} placeholder='مدت روز' value={planForm.duration_days} onChange={(event) => setPlanForm((value) => ({ ...value, duration_days: event.target.value }))} />
            <Input aria-label='سهمیه آگهی' type='number' min={0} placeholder='سهمیه آگهی' disabled={planForm.is_unlimited} value={planForm.listing_quota} onChange={(event) => setPlanForm((value) => ({ ...value, listing_quota: event.target.value }))} />
            <Input aria-label='سهمیه پیامک' type='number' min={0} placeholder='سهمیه پیامک' value={planForm.sms_quota} onChange={(event) => setPlanForm((value) => ({ ...value, sms_quota: event.target.value }))} />
            <Input aria-label='سهمیه مناطق' type='number' min={0} placeholder='سهمیه مناطق' value={planForm.regions_quota} onChange={(event) => setPlanForm((value) => ({ ...value, regions_quota: event.target.value }))} />
            <Input aria-label='سهمیه مشاور' type='number' min={0} placeholder='سهمیه مشاور' disabled={planForm.is_unlimited} value={planForm.advisor_quota} onChange={(event) => setPlanForm((value) => ({ ...value, advisor_quota: event.target.value }))} />
            <Input aria-label='ترتیب نمایش' type='number' min={0} placeholder='ترتیب نمایش' value={planForm.sort_order} onChange={(event) => setPlanForm((value) => ({ ...value, sort_order: event.target.value }))} />
            <Input aria-label='توضیحات پلن' placeholder='توضیحات پلن' value={planForm.description} onChange={(event) => setPlanForm((value) => ({ ...value, description: event.target.value }))} />
            <label className='flex items-center gap-2 text-sm'><input type='checkbox' checked={planForm.is_unlimited} onChange={(event) => setPlanForm((value) => ({ ...value, is_unlimited: event.target.checked, listing_quota: event.target.checked ? '' : value.listing_quota || '3', advisor_quota: event.target.checked ? '' : value.advisor_quota || '1' }))} />آگهی و مشاور نامحدود</label>
            <label className='flex items-center gap-2 text-sm'><input type='checkbox' checked={planForm.is_active} onChange={(event) => setPlanForm((value) => ({ ...value, is_active: event.target.checked }))} />فعال برای فروش</label>
            <textarea aria-label='ویژگی‌های پلن' className='min-h-20 rounded-md border bg-background p-3 text-sm lg:col-span-2' placeholder='هر ویژگی در یک خط' value={planForm.features} onChange={(event) => setPlanForm((value) => ({ ...value, features: event.target.value }))} />
          </div>
          <div className='flex flex-wrap gap-2'>
            <Button disabled={planMutation.isPending || !planForm.title.trim() || !planForm.price_toman || !planForm.duration_days || (!planForm.is_unlimited && (!planForm.listing_quota || !planForm.advisor_quota))} onClick={() => planMutation.mutate()}>{planMutation.isPending ? 'در حال ذخیره…' : editingPlan ? 'ذخیرهٔ تغییرات پلن' : 'ایجاد پلن'}</Button>
            {editingPlan && <Button variant='outline' onClick={() => { setEditingPlan(null); setPlanForm(emptyPlan); }}>لغو ویرایش</Button>}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>فیلتر سفارش‌ها</CardTitle><CardDescription>جست‌وجو و فیلتر روی Backend انجام می‌شود.</CardDescription></CardHeader>
        <CardContent className='grid gap-3 sm:grid-cols-3'>
          <Input aria-label='جست‌وجو بر اساس شماره سفارش' placeholder='شماره سفارش' value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} />
          <select aria-label='فیلتر وضعیت' className='h-10 rounded-md border bg-background px-3 text-sm' value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
            <option value=''>همه وضعیت‌ها</option><option value='receipt_submitted'>رسید ارسال‌شده</option><option value='under_review'>در حال بررسی</option><option value='approved'>تأییدشده</option><option value='rejected'>ردشده</option><option value='pending_payment'>در انتظار زیبال</option>
          </select>
          <select aria-label='فیلتر واقعی یا آزمایشی' className='h-10 rounded-md border bg-background px-3 text-sm' value={isTest} onChange={(event) => { setIsTest(event.target.value); setPage(1); }}>
            <option value=''>واقعی و آزمایشی</option><option value='false'>واقعی</option><option value='true'>آزمایشی</option>
          </select>
        </CardContent>
      </Card>
      {queue.data?.items.map((order: PaymentOrder) => <Card key={order.id}>
        <CardHeader><div className='flex flex-wrap items-center justify-between gap-2'><div><CardTitle>{order.order_number}</CardTitle><CardDescription>{toman(order.amount_toman)} تومان · پلن {order.plan} · {order.payment_method === 'ZIBAL' ? 'زیبال' : 'کارت‌به‌کارت'}</CardDescription></div><div className='flex gap-2'><Badge>{order.status}</Badge><Badge variant={order.is_test ? 'destructive' : 'default'}>{order.is_test ? 'آزمایشی — وجه واریز نشود' : 'واقعی'}</Badge></div></div></CardHeader>
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
      <div className='flex items-center justify-between gap-3'>
        <Button variant='outline' disabled={page <= 1 || queue.isPending} onClick={() => setPage((value) => Math.max(1, value - 1))}>صفحهٔ قبل</Button>
        <span className='text-sm text-muted-foreground'>صفحه {page}</span>
        <Button variant='outline' disabled={!queue.data || queue.data.items.length < queue.data.page_size} onClick={() => setPage((value) => value + 1)}>صفحهٔ بعد</Button>
      </div>

      <Card>
        <CardHeader>
          <div className='flex flex-wrap items-center justify-between gap-2'>
            <div><CardTitle>استعلام‌های زیبال</CardTitle><CardDescription>وضعیت تنها با Inquiry/Verify سرور تغییر می‌کند؛ موفقیت دستی یا از QueryString پذیرفته نمی‌شود.</CardDescription></div>
            <Button variant='outline' disabled={reconcileBatch.isPending || !attempts.data?.items.length} onClick={() => reconcileBatch.mutate()}>{reconcileBatch.isPending ? 'در حال استعلام…' : 'استعلام گروهی تراکنش‌های قدیمی'}</Button>
          </div>
        </CardHeader>
        <CardContent className='space-y-3'>
          {attempts.data?.items.map((attempt) => <div key={attempt.id} className='flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3'>
            <div className='min-w-56 flex-1 space-y-1 text-sm'><div className='font-medium'>{attempt.order_number ?? attempt.order_id}</div><div className='text-muted-foreground'>{toman(attempt.amount_toman)} تومان · تلاش {attempt.attempt_number} · {attempt.status}</div>{attempt.track_id && <div className='text-xs text-muted-foreground'>Track ID: {attempt.track_id}</div>}
              {(attempt.status === 'UNKNOWN' || attempt.status === 'PENDING') && <div className='flex flex-wrap items-center gap-2 pt-2'><Input aria-label='دلیل تعیین تکلیف عدم پرداخت' minLength={20} maxLength={1000} placeholder='پس از بررسی پنل زیبال، دلیل تأیید عدم پرداخت را وارد کنید' value={unpaidReasons[attempt.id] ?? ''} onChange={(event) => setUnpaidReasons((current) => ({ ...current, [attempt.id]: event.target.value }))} /><Button size='sm' variant='destructive' disabled={confirmNotPaid.isPending || (unpaidReasons[attempt.id] ?? '').trim().length < 20} onClick={() => confirmNotPaid.mutate({ id: attempt.id, reason: unpaidReasons[attempt.id] ?? '' })}>تأیید عدم پرداخت و لغو</Button></div>}
            </div>
            <Button size='sm' variant='outline' disabled={reconcile.isPending || !attempt.track_id} onClick={() => reconcile.mutate(attempt.id)}>استعلام مجدد</Button>
          </div>)}
          {attempts.isPending && <p className='text-sm text-muted-foreground'>در حال دریافت تراکنش‌ها…</p>}
          {!attempts.isPending && !attempts.data?.items.length && <p className='text-sm text-muted-foreground'>تراکنش بلاتکلیفی وجود ندارد.</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>گزارش ممیزی مالی</CardTitle><CardDescription>سوابق صدور سفارش، بررسی دستی، Callback و Reconciliation</CardDescription></CardHeader>
        <CardContent className='space-y-2'>
          {audits.data?.items.map((entry) => <div key={entry.id} className='grid gap-1 rounded-lg border p-3 text-xs sm:grid-cols-[1fr_1fr_1fr]'>
            <span>{entry.action}</span><span className='text-muted-foreground'>{entry.entity_type} · {entry.entity_id}</span><time className='text-muted-foreground'>{new Date(entry.created_at).toLocaleString('fa-IR')}</time>
          </div>)}
          {audits.isPending && <p className='text-sm text-muted-foreground'>در حال دریافت گزارش…</p>}
          {!audits.isPending && !audits.data?.items.length && <p className='text-sm text-muted-foreground'>رویدادی ثبت نشده است.</p>}
        </CardContent>
      </Card>
    </div>}
  </PageContainer>;
}
