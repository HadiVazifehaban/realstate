'use client';

import * as React from 'react';
import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { IconCopy } from '@tabler/icons-react';
import { Icons } from '@/components/icons';
import PageContainer from '@/components/layout/page-container';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import {
  fetchOrders,
  fetchPlans,
  fetchSubscription,
  fetchReferralSummary,
  fetchOrder,
  createOrder,
  startZibalCheckout,
  createBillingIdempotencyKey,
  previewOrder,
  submitReceipt,
  toman,
  groupedCard,
  type PaymentOrder,
  type BillingPaymentMethod
} from '@/features/billing/api/client';

const STATUS: Record<string, string> = {
  created: 'ایجادشده',
  pending_payment: 'در انتظار نتیجهٔ پرداخت آنلاین',
  awaiting_transfer: 'در انتظار واریز',
  receipt_submitted: 'رسید ثبت‌شده',
  under_review: 'در حال بررسی',
  test_approved_no_activation: 'تأیید آزمایشی — بدون فعال‌سازی',
  approved: 'تأیید و فعال‌شده',
  rejected: 'ردشده',
  expired: 'منقضی',
  cancelled: 'لغوشده'
};

const STATUS_VARIANT: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
  approved: 'default',
  rejected: 'destructive',
  expired: 'outline',
  cancelled: 'outline',
  awaiting_transfer: 'secondary',
  receipt_submitted: 'secondary',
  under_review: 'secondary'
};

function Metric({
  icon: Icon,
  label,
  value,
  detail
}: {
  icon: typeof Icons.billing;
  label: string;
  value: React.ReactNode;
  detail?: string;
}) {
  return (
    <div className='flex min-w-0 items-start gap-3 rounded-xl border border-border/70 bg-background/70 p-4'>
      <span className='flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary'>
        <Icon className='size-5' aria-hidden />
      </span>
      <div className='min-w-0'>
        <p className='text-xs text-muted-foreground'>{label}</p>
        <p className='mt-1 truncate text-lg font-bold tabular-nums'>{value}</p>
        {detail && <p className='mt-1 text-xs text-muted-foreground'>{detail}</p>}
      </div>
    </div>
  );
}

export default function BillingPage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = React.useState<PaymentOrder | null>(null);
  const [receiptFile, setReceiptFile] = React.useState<File | null>(null);
  const [tracking, setTracking] = React.useState('');
  const [transferAt, setTransferAt] = React.useState('');
  const [previewPlan, setPreviewPlan] = React.useState<string | null>(null);
  const [paymentMethod, setPaymentMethod] = React.useState<BillingPaymentMethod>('CARD_TO_CARD');
  const [returnedOrder, setReturnedOrder] = React.useState<PaymentOrder | null>(null);
  const createOrderIdempotencyKey = React.useRef<string | null>(null);
  const plans = useQuery({ queryKey: ['billing', 'plans'], queryFn: fetchPlans });
  const orders = useQuery({ queryKey: ['billing', 'orders'], queryFn: fetchOrders });
  const subscription = useQuery({ queryKey: ['billing', 'subscription'], queryFn: fetchSubscription });
  const referralSummary = useQuery({ queryKey: ['agency-referral'], queryFn: fetchReferralSummary });
  const preview = useQuery({
    queryKey: ['billing', 'preview', previewPlan],
    queryFn: () => previewOrder(previewPlan!),
    enabled: Boolean(previewPlan)
  });

  React.useEffect(() => {
    // Callback query parameters are never treated as proof of payment. Load the
    // order from the authenticated API and display its persisted state only.
    const orderId = new URLSearchParams(window.location.search).get('order_id');
    if (!orderId) return;
    void fetchOrder(orderId).then((order) => {
      setReturnedOrder(order);
      void queryClient.invalidateQueries({ queryKey: ['billing'] });
    }).catch((error: unknown) => {
      toast.error(error instanceof Error ? error.message : 'بررسی نتیجهٔ پرداخت ممکن نشد.');
    });
  }, [queryClient]);

  const create = useMutation({
    mutationFn: ({ planId, method, idempotencyKey }: { planId: string; method: BillingPaymentMethod; idempotencyKey: string }) => createOrder(planId, method, idempotencyKey),
    onSuccess: (order) => {
      createOrderIdempotencyKey.current = null;
      setPreviewPlan(null);
      void queryClient.invalidateQueries({ queryKey: ['billing'] });
      if (order.payment_method === 'ZIBAL') {
        if (order.payment_attempt?.status === 'PENDING' && order.payment_attempt.payment_url) {
          window.location.assign(order.payment_attempt.payment_url);
          return;
        }
        setSelected(order);
        if (order.payment_attempt?.status === 'UNKNOWN') {
          toast.error('نتیجهٔ درخواست درگاه نامشخص است؛ برای جلوگیری از پرداخت تکراری، سفارش را دوباره ارسال نکنید.');
        } else if (order.payment_attempt?.status === 'FAILED') {
          toast.error('درخواست پرداخت توسط درگاه شروع نشد؛ سفارش را می‌توانید دوباره تلاش کنید.');
        }
        return;
      }
      setSelected(order);
    },
    onError: (error) => toast.error(error.message)
  });
  const resumeZibal = useMutation({
    mutationFn: startZibalCheckout,
    onSuccess: (result) => {
      if (result.payment_attempt.status === 'PENDING' && result.payment_attempt.payment_url) {
        window.location.assign(result.payment_attempt.payment_url);
        return;
      }
      void queryClient.invalidateQueries({ queryKey: ['billing'] });
      toast.error(result.payment_attempt.status === 'UNKNOWN'
        ? 'نتیجهٔ درخواست زیبال نامشخص است؛ برای جلوگیری از پرداخت تکراری تا بررسی مالی صبر کنید.'
        : 'درگاه پرداخت آماده نشد؛ بعداً دوباره تلاش کنید.');
    },
    onError: (error) => toast.error(error.message)
  });
  const upload = useMutation({
    mutationFn: () => {
      if (!selected || !receiptFile) throw new Error('رسید را انتخاب کنید.');
      const transferDate = new Date(transferAt);
      if (!transferAt || Number.isNaN(transferDate.getTime())) throw new Error('زمان واریز را به‌درستی وارد کنید.');
      return submitReceipt(selected.id, {
        file: receiptFile,
        trackingNumber: tracking,
        transferDateTime: transferDate.toISOString()
      });
    },
    onSuccess: (result) => {
      toast.success(result.message);
      setSelected(null);
      setReceiptFile(null);
      setTracking('');
      setTransferAt('');
      void queryClient.invalidateQueries({ queryKey: ['billing'] });
    },
    onError: (error) => toast.error(error.message)
  });

  async function copyCard() {
    if (!selected?.card_number) return;
    try {
      await navigator.clipboard.writeText(groupedCard(selected.card_number));
      toast.success('شماره کارت کپی شد.');
    } catch {
      toast.error('کپی شماره کارت ممکن نشد.');
    }
  }

  const credits = referralSummary.data?.credits;
  const availableCredits = credits?.available ?? 0;
  const activeSubscription = subscription.data && subscription.data.status !== 'expired';

  return (
    <PageContainer
      pageTitle='اشتراک و پرداخت'
      pageDescription='مدیریت اشتراک، مشاهدهٔ اعتبارهای معرفی و پیگیری پرداخت‌ها'
    >
      <div className='mx-auto w-full max-w-7xl space-y-7' dir='rtl'>
        <section className='relative overflow-hidden rounded-2xl border border-primary/15 bg-gradient-to-br from-primary/[0.12] via-card to-card p-5 shadow-sm sm:p-7'>
          <div className='pointer-events-none absolute -left-12 -top-16 size-56 rounded-full bg-primary/10 blur-3xl' />
          <div className='relative grid gap-6 lg:grid-cols-[1.1fr_1fr] lg:items-center'>
            <div>
              <Badge variant='outline' className='mb-3 gap-1.5 border-primary/25 bg-background/60'>
                <Icons.sparkles className='size-3.5' aria-hidden />
                مرکز اشتراک
              </Badge>
              <h2 className='text-2xl font-bold tracking-tight sm:text-3xl'>همه‌چیز برای ادامهٔ کار آماده است؟</h2>
              <p className='mt-2 max-w-xl text-sm leading-6 text-muted-foreground'>
                پلن مناسب را انتخاب کنید، مبلغ نهایی را پیش از سفارش ببینید و پرداخت خود را از همین صفحه پیگیری کنید.
              </p>
              <a href='#plans' className='mt-5 inline-flex items-center gap-2 text-sm font-semibold text-primary hover:underline'>
                مشاهدهٔ پلن‌ها <Icons.chevronDown className='size-4' aria-hidden />
              </a>
            </div>
            <div className='grid gap-3 sm:grid-cols-2'>
              <Metric
                icon={Icons.pro}
                label='اشتراک فعلی'
                value={subscription.isPending ? '…' : subscription.data?.title ?? 'بدون اشتراک'}
                detail={subscription.data?.expires_at ? `پایان اعتبار: ${new Date(subscription.data.expires_at).toLocaleDateString('fa-IR')}` : 'پلن دلخواهتان را انتخاب کنید'}
              />
              <Metric
                icon={Icons.referral}
                label='اعتبار معرفی آمادهٔ استفاده'
                value={`${toman(availableCredits)} اعتبار`}
                detail={availableCredits > 0 ? 'برای تمدید اشتراک قابل استفاده است' : 'با معرفی دفترهای جدید اعتبار بگیرید'}
              />
            </div>
          </div>
        {subscription.isError && (
            <p className='relative mt-4 text-sm text-destructive'>دریافت وضعیت اشتراک ممکن نشد.</p>
          )}
        </section>

        {activeSubscription && subscription.data && (
          <Card className='border-border/70'>
            <CardHeader className='pb-3'>
              <CardTitle className='flex items-center gap-2 text-base'>
                <Icons.circleCheck className='size-5 text-emerald-600' aria-hidden />
                جزئیات اشتراک فعال
              </CardTitle>
              <CardDescription>سهمیه‌های فعلی حساب شما</CardDescription>
            </CardHeader>
            <CardContent className='grid gap-3 sm:grid-cols-2 xl:grid-cols-4'>
              <Metric icon={Icons.home} label='مصرف آگهی (مصرف‌شده / سقف)' value={subscription.data.quota?.listings.unlimited ? 'نامحدود' : `${subscription.data.quota?.listings.used ?? subscription.data.usage.listings ?? 0} / ${subscription.data.quota?.listings.limit ?? subscription.data.listing_quota ?? 0}`} />
              <Metric icon={Icons.activity} label='پیامک رادار لید' value={toman(subscription.data.sms_quota)} />
              <Metric icon={Icons.mapPin} label='مناطق فایلینگ' value={toman(subscription.data.regions_quota)} />
              <Metric icon={Icons.user} label='مشاور' value={subscription.data.advisor_quota == null ? 'نامحدود' : toman(subscription.data.advisor_quota)} />
            </CardContent>
          </Card>
        )}

        {returnedOrder && (
          <Alert variant={returnedOrder.status === 'approved' ? 'default' : returnedOrder.status === 'test_approved_no_activation' ? 'destructive' : 'default'}>
            <Icons.info aria-hidden />
            <AlertDescription>
              {returnedOrder.status === 'approved'
                ? `پرداخت سفارش ${returnedOrder.order_number} در سرور تأیید شد.`
                : returnedOrder.status === 'test_approved_no_activation'
                  ? `پرداخت آزمایشی سفارش ${returnedOrder.order_number} اشتراک را فعال نمی‌کند.`
                  : `وضعیت سفارش ${returnedOrder.order_number}: ${STATUS[returnedOrder.status] ?? returnedOrder.status}. نتیجه را فقط از وضعیت ثبت‌شدهٔ سرور دنبال کنید.`}
            </AlertDescription>
          </Alert>
        )}

        <section id='plans' className='scroll-mt-6 space-y-4'>
          <div className='flex flex-wrap items-end justify-between gap-2'>
            <div>
              <h2 className='text-xl font-bold'>انتخاب پلن</h2>
              <p className='mt-1 text-sm text-muted-foreground'>امکانات و سهمیه‌ها را مقایسه کنید؛ مبلغ نهایی پیش از ایجاد سفارش نمایش داده می‌شود.</p>
            </div>
              <Badge variant='outline' className='gap-1.5'>
              <Icons.shield className='size-3.5' aria-hidden /> روش‌های پرداخت فعال از سرور دریافت می‌شوند
            </Badge>
          </div>

          {plans.isPending && <div className='grid gap-4 md:grid-cols-2 xl:grid-cols-4' aria-label='در حال دریافت پلن‌ها'>{[1, 2, 3, 4].map((item) => <div key={item} className='h-64 animate-pulse rounded-2xl border bg-muted/40' />)}</div>}
          {plans.isError && (
            <Alert variant='destructive'>
              <Icons.alertCircle aria-hidden />
              <AlertDescription className='flex flex-wrap items-center justify-between gap-3'>
                دریافت پلن‌ها ناموفق بود. اتصال را بررسی و دوباره تلاش کنید.
                <Button size='sm' variant='outline' onClick={() => void plans.refetch()}>تلاش دوباره</Button>
              </AlertDescription>
            </Alert>
          )}
          {plans.data && plans.data.plans.length === 0 && <p className='rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground'>در حال حاضر پلنی برای نمایش وجود ندارد.</p>}

          {plans.data && plans.data.plans.length > 0 && (
            <div className='grid items-stretch gap-4 md:grid-cols-2 xl:grid-cols-4'>
              {plans.data.plans.map((plan) => {
                const isCurrent = subscription.data?.plan === plan.id && activeSubscription;
                return (
                  <Card key={plan.id} className={`relative flex min-w-0 flex-col overflow-hidden rounded-2xl transition-shadow hover:shadow-md ${isCurrent ? 'border-primary/50 shadow-sm ring-1 ring-primary/20' : 'border-border/70'}`}>
                    {isCurrent && <div className='absolute inset-x-0 top-0 h-1 bg-primary' />}
                    <CardHeader className='pb-3'>
                      <div className='flex items-start justify-between gap-2'>
                        <div>
                          <CardTitle className='text-lg'>{plan.title}</CardTitle>
                          <CardDescription className='mt-1'>{plan.duration_days === 0 ? 'بدون محدودیت زمانی' : `${toman(plan.duration_days)} روز`}</CardDescription>
                        </div>
                        {isCurrent && <Badge>پلن فعلی</Badge>}
                      </div>
                      <p className='pt-3 text-2xl font-extrabold tracking-tight text-primary'>
                        {plan.price_toman === 0 ? 'رایگان' : <>{toman(plan.price_toman)} <span className='text-sm font-medium text-muted-foreground'>تومان</span></>}
                      </p>
                    </CardHeader>
                    <CardContent className='flex flex-1 flex-col gap-4'>
                      <ul className='space-y-3 border-y py-4 text-sm'>
                        <li className='flex items-center justify-between gap-3'><span className='text-muted-foreground'>آگهی</span><span className='font-medium'>{plan.is_unlimited ? 'نامحدود*' : toman(plan.listing_quota ?? 0)}</span></li>
                        <li className='flex items-center justify-between gap-3'><span className='text-muted-foreground'>پیامک رادار لید</span><span className='font-medium'>{toman(plan.sms_quota)}</span></li>
                        <li className='flex items-center justify-between gap-3'><span className='text-muted-foreground'>مناطق فایلینگ</span><span className='font-medium'>{toman(plan.regions_quota)}</span></li>
                        <li className='flex items-center justify-between gap-3'><span className='text-muted-foreground'>مشاور</span><span className='font-medium'>{plan.advisor_quota == null ? 'نامحدود*' : toman(plan.advisor_quota)}</span></li>
                      </ul>
                      {plan.features.length > 0 && <ul className='space-y-2 text-sm text-muted-foreground'>{plan.features.map((feature) => <li key={feature} className='flex gap-2'><Icons.check className='mt-0.5 size-4 shrink-0 text-emerald-600' aria-hidden /><span>{feature}</span></li>)}</ul>}
                      <div className='mt-auto pt-2'>
                        {plan.id !== 'free' ? (
                          <Button className='w-full gap-2' disabled={create.isPending} onClick={() => { createOrderIdempotencyKey.current = null; setPaymentMethod('CARD_TO_CARD'); setPreviewPlan(plan.id); void preview.refetch(); }}>
                            <Icons.receipt className='size-4' aria-hidden />
                            {isCurrent ? 'تمدید یا ارتقا' : 'انتخاب و مشاهدهٔ مبلغ'}
                          </Button>
                        ) : <p className='rounded-lg bg-muted/60 px-3 py-2 text-center text-xs text-muted-foreground'>* نامحدود طبق سیاست استفادهٔ منصفانه</p>}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </section>

        {previewPlan && (
          <Card className='overflow-hidden border-primary/30 shadow-sm'>
            <CardHeader className='bg-primary/[0.045]'>
              <CardTitle className='flex items-center gap-2 text-lg'><Icons.receipt className='size-5 text-primary' aria-hidden /> پیش‌نمایش صورتحساب</CardTitle>
              <CardDescription>مبلغ نهایی سفارش هنگام ایجاد، دوباره در سرور محاسبه و تأیید می‌شود.</CardDescription>
            </CardHeader>
            <CardContent className='space-y-4 pt-5'>
              {preview.isFetching && <p className='text-sm text-muted-foreground'>در حال محاسبهٔ مبلغ نهایی…</p>}
              {preview.isError && <Alert variant='destructive'><Icons.alertCircle aria-hidden /><AlertDescription>محاسبهٔ مبلغ ناموفق بود. <button className='underline underline-offset-4' onClick={() => void preview.refetch()}>تلاش دوباره</button></AlertDescription></Alert>}
              {preview.data && (
                <>
                  <div className='space-y-3 text-sm'>
                    <div className='flex justify-between gap-4'><span className='text-muted-foreground'>مبلغ پایه</span><span className='font-medium tabular-nums'>{toman(preview.data.base_amount_toman)} تومان</span></div>
                    <div className='flex justify-between gap-4'><span className='text-muted-foreground'>تخفیف اعتبار معرفی ({preview.data.referral_discount_percent}٪ · {toman(preview.data.referral_credit_count)} اعتبار)</span><span className='font-medium text-emerald-700 tabular-nums'>− {toman(preview.data.referral_discount_toman)} تومان</span></div>
                    <div className='border-t pt-3'><div className='flex justify-between gap-4 text-base font-bold'><span>مبلغ قابل پرداخت</span><span className='text-primary tabular-nums'>{toman(preview.data.amount_toman)} تومان</span></div></div>
                  </div>
                  {preview.data.referral_discount_percent === 0 && <p className='rounded-lg bg-muted/60 p-3 text-xs leading-5 text-muted-foreground'>{availableCredits > 0 ? 'اعتبارهای معرفی شما برای تمدید اشتراک قابل استفاده‌اند و در خرید نخست اعمال نمی‌شوند.' : 'در این سفارش اعتبار معرفی قابل استفاده‌ای وجود ندارد.'}</p>}
                  <fieldset className='space-y-2 rounded-xl border p-4' disabled={create.isPending}>
                    <legend className='px-1 text-sm font-semibold'>روش پرداخت</legend>
                    <label className='flex cursor-pointer items-start gap-3 rounded-lg p-2 hover:bg-muted/40'>
                      <input
                        type='radio'
                        name='billing-payment-method'
                        value='CARD_TO_CARD'
                        checked={paymentMethod === 'CARD_TO_CARD'}
                        disabled={!plans.data?.payment_methods.CARD_TO_CARD}
                        onChange={() => setPaymentMethod('CARD_TO_CARD')}
                        className='mt-1 accent-primary'
                      />
                      <span><span className='block text-sm font-medium'>کارت‌به‌کارت</span><span className='text-xs text-muted-foreground'>رسید پس از ارسال توسط مدیر مالی بررسی می‌شود.</span></span>
                    </label>
                    <label className={`flex items-start gap-3 rounded-lg p-2 ${plans.data?.payment_methods.ZIBAL ? 'cursor-pointer hover:bg-muted/40' : 'cursor-not-allowed opacity-50'}`}>
                      <input
                        type='radio'
                        name='billing-payment-method'
                        value='ZIBAL'
                        checked={paymentMethod === 'ZIBAL'}
                        disabled={!plans.data?.payment_methods.ZIBAL}
                        onChange={() => setPaymentMethod('ZIBAL')}
                        className='mt-1 accent-primary'
                      />
                      <span><span className='block text-sm font-medium'>درگاه آنلاین زیبال</span><span className='text-xs text-muted-foreground'>
                        {plans.data?.payment_methods.ZIBAL
                          ? plans.data.payment_methods.ZIBAL_TEST_MODE ? 'حالت آزمایشی؛ اشتراک فعال نمی‌شود.' : 'تأیید نهایی از سرور زیبال انجام می‌شود.'
                          : 'تا زمان تنظیم امن Merchant و Callback در سرور غیرفعال است.'}
                      </span></span>
                    </label>
                  </fieldset>
                  <div className='flex flex-col-reverse gap-2 sm:flex-row sm:justify-start'>
                    <Button variant='outline' onClick={() => { createOrderIdempotencyKey.current = null; setPreviewPlan(null); }}>بازگشت به پلن‌ها</Button>
                    <Button className='gap-2' disabled={create.isPending || (paymentMethod === 'CARD_TO_CARD' && !plans.data?.payment_methods.CARD_TO_CARD) || (paymentMethod === 'ZIBAL' && !plans.data?.payment_methods.ZIBAL)} onClick={() => {
                      createOrderIdempotencyKey.current ??= createBillingIdempotencyKey();
                      create.mutate({ planId: previewPlan!, method: paymentMethod, idempotencyKey: createOrderIdempotencyKey.current });
                    }}>
                      {create.isPending ? <Icons.spinner className='size-4 animate-spin' aria-hidden /> : <Icons.creditCard className='size-4' aria-hidden />}
                      {paymentMethod === 'ZIBAL' ? 'ایجاد سفارش و رفتن به زیبال' : 'ایجاد سفارش و دریافت دستور پرداخت'}
                    </Button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        )}

        {selected && (
          <Card className='overflow-hidden border-primary/35'>
            <CardHeader className='bg-primary/[0.045]'>
              <CardTitle className='flex flex-wrap items-center justify-between gap-2'>
                <span>دستور پرداخت</span><Badge variant='outline' className='font-mono'>{selected.order_number}</Badge>
              </CardTitle>
              <CardDescription>مبلغ سفارش: <strong className='text-foreground'>{toman(selected.amount_toman)} تومان</strong></CardDescription>
            </CardHeader>
            <CardContent className='space-y-4 pt-5'>
              {selected.discount_percent > 0 && <div className='rounded-xl border border-emerald-600/20 bg-emerald-600/[0.05] p-3 text-sm leading-6'>مبلغ پایه {toman(selected.base_amount_toman)} تومان · تخفیف معرفی {selected.discount_percent}٪ ({toman(selected.discount_amount_toman)} تومان، {toman(selected.referral_credit_count)} اعتبار) · مبلغ پرداختی <strong>{toman(selected.amount_toman)} تومان</strong></div>}
              {selected.is_test && <Alert variant='destructive'><Icons.warning aria-hidden /><AlertDescription>{selected.payment_method === 'ZIBAL' ? 'این پرداخت زیبال در حالت آزمایشی است؛ وجه واقعی نپردازید و اشتراک فعال نمی‌شود.' : 'این سفارش آزمایشی است. وجهی واریز نکنید؛ شماره کارت نمایش‌داده‌شده معتبر نیست.'}</AlertDescription></Alert>}
              {selected.payment_method === 'ZIBAL' && selected.payment_attempt && (
                <Alert variant={selected.payment_attempt.status === 'FAILED' ? 'destructive' : 'default'}>
                  <Icons.info aria-hidden />
                  <AlertDescription className='flex flex-wrap items-center justify-between gap-3'>
                    <span>وضعیت تلاش زیبال: {selected.payment_attempt.status}. پرداخت فقط پس از تأیید سرور ثبت می‌شود.</span>
                    {selected.payment_attempt.status === 'FAILED' && <Button size='sm' disabled={resumeZibal.isPending} onClick={() => resumeZibal.mutate(selected.id)}>{resumeZibal.isPending ? 'در حال تلاش…' : 'تلاش دوباره'}</Button>}
                  </AlertDescription>
                </Alert>
              )}
              {!selected.is_test && selected.card_number && (
                <div className='flex flex-col gap-3 rounded-xl border bg-background p-4 sm:flex-row sm:items-center sm:justify-between'>
                  <div><p className='text-xs text-muted-foreground'>شماره کارت مقصد</p><p className='mt-1 font-mono text-xl tracking-widest' dir='ltr'>{groupedCard(selected.card_number)}</p><p className='mt-1 text-xs text-muted-foreground'>{selected.card_holder}</p></div>
                  <Button variant='outline' className='gap-2' onClick={() => void copyCard()}><IconCopy className='size-4' aria-hidden /> کپی شماره کارت</Button>
                </div>
              )}
              {!selected.card_configured && !selected.is_test && <Alert><Icons.info aria-hidden /><AlertDescription>اطلاعات کارت مقصد هنوز تنظیم نشده است. لطفاً بعداً دوباره تلاش کنید.</AlertDescription></Alert>}
              <div className='flex flex-wrap gap-2'>
                {selected.status === 'awaiting_transfer' && <Button onClick={() => { setTracking(''); setTransferAt(''); setReceiptFile(null); setSelected(selected); }}>ثبت رسید پرداخت</Button>}
                <Button variant='outline' onClick={() => setSelected(null)}>بستن دستور پرداخت</Button>
              </div>
            </CardContent>
          </Card>
        )}

        <Card className='overflow-hidden'>
          <CardHeader className='flex flex-row items-start justify-between gap-3 border-b bg-muted/20'>
            <div><CardTitle className='flex items-center gap-2 text-lg'><Icons.receipt className='size-5 text-primary' aria-hidden /> تاریخچهٔ پرداخت‌ها</CardTitle><CardDescription className='mt-1'>سفارش‌ها، مبلغ‌ها و وضعیت رسیدهای ارسالی</CardDescription></div>
            <Badge variant='outline'>{orders.data?.items.length ?? 0} سفارش</Badge>
          </CardHeader>
          <CardContent className='p-0'>
            {orders.isPending && <div className='space-y-3 p-5' aria-label='در حال دریافت سفارش‌ها'>{[1, 2, 3].map((item) => <div key={item} className='h-16 animate-pulse rounded-lg bg-muted/60' />)}</div>}
            {orders.isError && <div className='flex flex-wrap items-center justify-between gap-3 p-5 text-sm'><span className='text-destructive'>دریافت تاریخچهٔ پرداخت ناموفق بود.</span><Button size='sm' variant='outline' onClick={() => void orders.refetch()}>تلاش دوباره</Button></div>}
            {orders.data && orders.data.items.length > 0 && <div className='divide-y'>{orders.data.items.map((order) => (
              <div key={order.id} className='flex flex-col gap-3 p-4 transition-colors hover:bg-muted/20 sm:flex-row sm:items-center sm:justify-between'>
                <div className='flex min-w-0 items-start gap-3'>
                  <span className='flex size-10 shrink-0 items-center justify-center rounded-xl bg-muted text-muted-foreground'><Icons.wallet className='size-5' aria-hidden /></span>
                  <div className='min-w-0'><p className='truncate font-semibold'>{order.order_number}</p><p className='mt-1 text-xs text-muted-foreground'>{new Date(order.created_at).toLocaleString('fa-IR')} · پلن {order.plan}</p></div>
                </div>
                <div className='flex flex-wrap items-center gap-2 sm:justify-end'>
                  <span className='ms-1 font-semibold tabular-nums'>{toman(order.amount_toman)} <span className='text-xs font-normal text-muted-foreground'>تومان</span></span>
                  <Badge variant={order.is_test ? 'outline' : 'secondary'}>{order.is_test ? 'آزمایشی' : 'واقعی'}</Badge>
                  <Badge variant={STATUS_VARIANT[order.status] ?? 'outline'}>{STATUS[order.status] ?? order.status}</Badge>
                  {order.status === 'awaiting_transfer' && <Button size='sm' variant='outline' onClick={() => setSelected(order)}>ثبت رسید</Button>}
                  {order.payment_method === 'ZIBAL' && order.payment_attempt?.status === 'PENDING' && order.payment_attempt.payment_url && <Button size='sm' variant='outline' onClick={() => window.location.assign(order.payment_attempt!.payment_url!)}>ادامهٔ پرداخت</Button>}
                  {order.payment_method === 'ZIBAL' && order.payment_attempt?.status === 'FAILED' && <Button size='sm' variant='outline' disabled={resumeZibal.isPending} onClick={() => resumeZibal.mutate(order.id)}>تلاش دوبارهٔ زیبال</Button>}
                </div>
              </div>
            ))}</div>}
            {!orders.isPending && !orders.isError && !orders.data?.items.length && <div className='flex flex-col items-center px-5 py-10 text-center'><span className='mb-3 flex size-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground'><Icons.inbox className='size-6' aria-hidden /></span><p className='font-medium'>هنوز پرداختی ثبت نشده است</p><p className='mt-1 text-sm text-muted-foreground'>پس از انتخاب پلن، سفارش‌های شما در این بخش نمایش داده می‌شوند.</p></div>}
          </CardContent>
          <div className='border-t bg-muted/10 px-4 py-3'><Link className='inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline' href='/dashboard/billing/financial'>ورود به پنل بررسی مالی <Icons.chevronLeft className='size-4' aria-hidden /></Link></div>
        </Card>
      </div>

      <Dialog open={Boolean(selected && selected.status === 'awaiting_transfer')} onOpenChange={(open) => { if (!open) { setSelected(null); setReceiptFile(null); } }}>
        <DialogContent className='sm:max-w-lg' dir='rtl'>
          <DialogHeader>
            <DialogTitle>ثبت رسید پرداخت</DialogTitle>
            <DialogDescription>اطلاعات انتقال وجه و تصویر رسید را برای بررسی مدیر مالی ثبت کنید.</DialogDescription>
          </DialogHeader>
          {selected && <div className='space-y-4'>
            <div className='rounded-lg bg-muted/50 p-3 text-sm'><span className='text-muted-foreground'>سفارش </span><span className='font-mono font-semibold'>{selected.order_number}</span><span className='mx-2 text-muted-foreground'>·</span><span className='font-semibold'>{toman(selected.amount_toman)} تومان</span></div>
            <div className='space-y-2'><Label htmlFor='receipt-file'>تصویر رسید</Label><Input id='receipt-file' type='file' accept='image/*,application/pdf' onChange={(event) => setReceiptFile(event.target.files?.[0] ?? null)} /><p className='text-xs text-muted-foreground'>{receiptFile ? `فایل انتخاب‌شده: ${receiptFile.name}` : 'تصویر یا فایل PDF رسید را انتخاب کنید.'}</p></div>
            <div className='space-y-2'><Label htmlFor='tracking-number'>شمارهٔ پیگیری</Label><Input id='tracking-number' value={tracking} onChange={(event) => setTracking(event.target.value)} placeholder='شمارهٔ درج‌شده روی رسید' /></div>
            <div className='space-y-2'><Label htmlFor='transfer-date'>زمان واریز</Label><Input id='transfer-date' type='datetime-local' value={transferAt} onChange={(event) => setTransferAt(event.target.value)} /></div>
          </div>}
          <DialogFooter>
            <Button variant='outline' onClick={() => setSelected(null)}>انصراف</Button>
            <Button disabled={!receiptFile || !tracking.trim() || !transferAt || upload.isPending} onClick={() => upload.mutate()}>
              {upload.isPending && <Icons.spinner className='me-2 size-4 animate-spin' aria-hidden />}ارسال رسید
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageContainer>
  );
}
