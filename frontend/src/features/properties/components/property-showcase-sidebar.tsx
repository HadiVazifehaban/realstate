"use client";

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { Icons } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { Modal } from '@/components/ui/modal';
import { useReportProperty } from '../hooks';
import type { PropertySummary, ReportReason } from '../types';
import {
  DEAL_TYPE_LABELS,
  PROPERTY_TYPE_LABELS,
  SOURCE_LABELS,
  SOURCE_TRUSTED,
  SUBMITTER_LABELS,
  VALUATION_LABELS,
  formatBuildingAge,
  formatPublishedAgo
} from '../utils/labels';
import { cn, formatToman, toPersianDigits } from '@/lib/utils';
import { useAuthContext } from '@/hooks/use-auth';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import Link from 'next/link';

/**
 * The listing's financial, legal and contact column.
 *
 * Everything here is gated on data the API actually returns. That constraint is
 * the reason several portal-familiar chips are deliberately absent: the showcase
 * treatment shows "تمدید" (renewed) and "نظارت‌شده" (supervised) badges and a
 * masked advisor phone, and this node has no signal for any of the three --
 * `renewed_at`, a supervision flag, or an advisor phone number. Rendering them
 * anyway would be inventing three facts a broker might act on. What replaces
 * each is real:
 *
 *   - renewed / supervised  -> provenance (which portal, and whether it is a
 *     first-party registration) plus the valuation verdict;
 *   - masked advisor phone -> the CRM handoff, which is how this office
 *     actually reaches a seller. Owner PII stays in the encrypted vault behind
 *     the CRM reveal flow and is never rendered on a public listing page.
 */

/** Advisory copy in the warning dialog. Deliberately generic legal caution. */
const TRANSACTION_WARNINGS = [
  'قبل از پرداخت هرگونه وجه، از اصالت سند و مالکیت مطمئن شوید.',
  'حتماً از ملک بازدید حضوری به عمل آورید.',
  'قرارداد را در دفاتر اسناد رسمی تنظیم کنید.',
  'از پرداشت وجه نقد بدون رسید خودداری کنید.',
  'شماره تماس مشاور را از طریق سایت‌های معتبر استعلام کنید.'
];

const REPORT_REASON_LABELS: Record<ReportReason, string> = {
  wrong_price: 'قیمت نادرست',
  outdated: 'آگهی منقضی شده',
  duplicate: 'آگهی تکراری',
  misleading: 'اطلاعات گمراه‌کننده',
  fraud: 'مشکوک به کلاهبرداری',
  other: 'سایر'
};

interface PropertyShowcaseSidebarProps {
  property: PropertySummary;
  /** Notified after a lead is filed, so the page can route to the CRM board. */
  onLeadCreated?: () => void;
  /** Dense grid treatment used by the single-viewport property detail page. */
  compact?: boolean;
}

export function PropertyShowcaseSidebar({
  property,
  onLeadCreated,
  compact = false
}: PropertyShowcaseSidebarProps) {
  const { user, isLoading: authLoading } = useAuthContext();
  const [warningOpen, setWarningOpen] = React.useState(false);
  const [reportOpen, setReportOpen] = React.useState(false);

  const location = [property.neighborhood, property.city].filter(Boolean).join('، ');
  const title =
    property.title ||
    `${PROPERTY_TYPE_LABELS[property.property_type]}${location ? ` در ${location}` : ''}`;
  const publishedAgo = formatPublishedAgo(property.updated_at);
  const isRent = property.deal_type === 'RENT' || property.deal_type === 'FULL_MORTGAGE';

  return (
    <div className={cn('flex min-w-0 flex-col gap-2.5', compact && 'property-detail-sidebar')}>
      <TitleCard property={property} title={title} location={location} publishedAgo={publishedAgo} compact={compact} />
      <StatsCard property={property} compact={compact} />
      <PriceCard property={property} isRent={isRent} compact={compact} />
      <AmenitiesCard property={property} compact={compact} />

      <div className={cn('flex flex-col gap-2', compact && 'property-detail-actions')}>
        <ActionRow
          icon={<Icons.warning className='size-4' />}
          tone='warning'
          label={compact ? 'هشدار معامله' : 'هشدارهای مهم قبل از معامله'}
          onClick={() => setWarningOpen(true)}
        />
        <ActionRow
          icon={<Icons.report className='size-4' />}
          tone='report'
          label={compact ? 'گزارش آگهی' : 'ارسال گزارش اشکال در آگهی'}
          onClick={() => setReportOpen(true)}
        />
      </div>

      <DescriptionCard property={property} compact={compact} />
      <AdvisorCard property={property} onLeadCreated={onLeadCreated} compact={compact} />

      {user && (
        <Modal
          title='هشدارهای مهم قبل از معامله'
          description='این موارد را پیش از هر پرداختی در نظر بگیرید.'
          isOpen={warningOpen}
          onClose={() => setWarningOpen(false)}
        >
          <ul className='text-showcase-muted mb-6 flex flex-col gap-2 text-xs leading-7'>
            {TRANSACTION_WARNINGS.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
          <Button className='w-full' onClick={() => setWarningOpen(false)}>متوجه شدم</Button>
        </Modal>
      )}

      {user && <ReportDialog propertyId={property.id} open={reportOpen} onClose={() => setReportOpen(false)} />}
      <GuestActionDialog open={!user && !authLoading && (warningOpen || reportOpen)} propertyId={property.id} onClose={() => { setWarningOpen(false); setReportOpen(false); }} />
    </div>
  );
}

function GuestActionDialog({ open, propertyId, onClose }: { open: boolean; propertyId: string; onClose: () => void }) {
  const callbackUrl = `/dashboard/properties/${encodeURIComponent(propertyId)}`;
  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) onClose(); }}>
      <DialogContent dir='rtl'>
        <DialogHeader>
          <DialogTitle>برای استفاده از این قابلیت وارد شکارچی شوید</DialogTitle>
          <DialogDescription>با ورود یا عضویت در شکارچی می‌توانید از امکانات اختصاصی این بخش استفاده کنید.</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Link className='inline-flex min-h-10 items-center justify-center rounded-md bg-primary px-4 text-primary-foreground' href={`/auth/sign-in?callbackUrl=${encodeURIComponent(callbackUrl)}`}>ورود / عضویت</Link>
          <button type='button' className='min-h-10 rounded-md border px-4' onClick={onClose}>انصراف</button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ------------------------------------------------------------------ title --- */

function TitleCard({
  property,
  title,
  location,
  publishedAgo,
  compact = false
}: {
  property: PropertySummary;
  title: string;
  location: string;
  publishedAgo: string | null;
  compact?: boolean;
}) {
  const dealLabel = DEAL_TYPE_LABELS[property.deal_type];
  const propertyLabel = PROPERTY_TYPE_LABELS[property.property_type];

  return (
    <section className={cn('showcase-panel p-3 sm:p-3.5', compact && 'property-detail-title')}>
      <div className='mb-2 flex flex-wrap gap-1.5'>
        <Badge tone='source'>{SOURCE_LABELS[property.source]}</Badge>
        {/* Who filed it, kept separate from where the row came from. A broker
            filing for a private owner reads «بنگاه» while the owner contacts
            below stay the owner's. Only rendered when the node actually knows:
            a scraped listing has no submitter to name. */}
        {property.submitter_type && (
          <Badge tone={property.submitter_type === 'PERSON' ? 'trusted' : 'source'}>
            {SUBMITTER_LABELS[property.submitter_type]}
          </Badge>
        )}
        {/* A first-party registration is the only case the node can attest to, so
            it is the only one that claims to be an owner listing. */}
        {property.submitter_type === 'PERSON' && <Badge tone='trusted'>مالک مستقیم</Badge>}
        {property.valuation_status !== 'UNKNOWN' && (
          <Badge tone='valuation'>{VALUATION_LABELS[property.valuation_status]}</Badge>
        )}
      </div>

      <h1 className='mb-1.5 text-base leading-relaxed font-extrabold text-white'>{title}</h1>
      <p className='text-showcase-muted mb-2 text-xs'>
        {`${dealLabel} ${propertyLabel}`}
        {location ? `، ${location}` : ''}
      </p>
      {publishedAgo && (
        <p className='text-showcase-dim flex items-center gap-1.5 text-[0.7rem]'>
          <Icons.clock className='size-3.5' />
          {publishedAgo}
        </p>
      )}
    </section>
  );
}

function Badge({
  tone,
  children
}: {
  tone: 'source' | 'trusted' | 'valuation';
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[0.68rem] font-bold',
        tone === 'trusted' &&
          'border border-showcase-success/35 bg-showcase-success/12 text-showcase-success',
        tone === 'valuation' &&
          'border border-sky-400/30 bg-sky-400/12 text-sky-300',
        tone === 'source' &&
          'border border-white/10 bg-white/5 text-showcase-muted'
      )}
    >
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ stats --- */

/** Cells are fixed-width and render an explicit dash, never collapse. */
function StatsCard({ property, compact = false }: { property: PropertySummary; compact?: boolean }) {
  const age = formatBuildingAge(property.year_built);

  const cells = [
    {
      label: 'مساحت ملک',
      value: property.area !== null ? toPersianDigits(property.area.toLocaleString('en-US')) : '—',
      unit: property.area !== null ? 'متر' : null
    },
    { label: 'عمر تقریبی بنا', value: age ?? '—', unit: null },
    {
      label: 'طبقه',
      value:
        property.floor !== null
          ? toPersianDigits(property.floor.toLocaleString('en-US'))
          : '—',
      unit:
        property.floor !== null && property.total_floors !== null
          ? `از ${toPersianDigits(property.total_floors.toLocaleString('en-US'))}`
          : null
    },
    {
      label: 'تعداد اتاق',
      value: property.rooms !== null ? toPersianDigits(property.rooms.toLocaleString('en-US')) : '—',
      unit: null
    }
  ];

  return (
    <section className={cn('showcase-panel min-w-0 p-1.5 sm:p-2', compact && 'property-detail-stats')}>
      <div className='grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-gold-primary/15 bg-gold-primary/12'>
        {cells.map((cell) => (
          <div key={cell.label} className='bg-showcase-surface-solid min-w-0 px-2 py-2.5 text-center'>
            <div className='text-sm font-extrabold leading-tight text-white tabular-nums'>
              {cell.value}
              {cell.unit && <span className='text-gold-primary ms-1 text-[0.7rem] font-semibold'>{cell.unit}</span>}
            </div>
            <div className='text-showcase-muted mt-0.5 text-[0.66rem]'>{cell.label}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ price --- */

function PriceCard({ property, isRent, compact = false }: { property: PropertySummary; isRent: boolean; compact?: boolean }) {
  // A rent listing has no total price by design -- quoting one would be a
  // fabricated number. Deposit + monthly is how the portals present it.
  const cells = isRent
    ? [
        { label: 'ودیعه', value: property.deposit_amount },
        { label: 'اجاره ماهانه', value: property.monthly_rent }
      ]
    : [
        { label: 'قیمت کل', value: property.total_price },
        { label: 'قیمت هر متر', value: property.price_per_meter }
      ];

  const bothNull = cells.every((cell) => cell.value === null);

  return (
    <section className={cn('showcase-panel p-1.5 sm:p-2', compact && 'property-detail-price')}>
      <div className='grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-gold-accent/25 bg-gold-primary/15'>
        {cells.map((cell, index) => (
          <div key={cell.label} className='bg-showcase-surface-solid px-3 py-3 text-center'>
            <div className='text-showcase-muted mb-1 text-[0.7rem]'>{cell.label}</div>
            <div
              className={cn(
                'text-sm font-extrabold leading-tight tabular-nums',
                cell.value === null ? 'text-showcase-dim' : index === 1 ? 'text-gold-primary' : 'text-white'
              )}
            >
              {bothNull
                ? '—'
                : cell.value !== null
                  ? formatToman(cell.value)
                  : 'ثبت نشده'}
              {cell.value !== null && (
                <span className='text-showcase-muted ms-1 text-[0.7rem] font-semibold'>تومان</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* -------------------------------------------------------------- amenities --- */

/** All four are always shown: a crossed-out amenity is decision-relevant. */
const AMENITIES = [
  { key: 'has_parking', label: 'پارکینگ', icon: Icons.amenityParking },
  { key: 'has_elevator', label: 'آسانسور', icon: Icons.amenityElevator },
  { key: 'has_storage', label: 'انباری', icon: Icons.amenityStorage },
  { key: 'has_balcony', label: 'بالکن', icon: Icons.amenityBalcony }
] as const;

function AmenitiesCard({ property, compact = false }: { property: PropertySummary; compact?: boolean }) {
  return (
    <section className={cn('showcase-panel p-3 sm:p-4', compact && 'property-detail-amenities')}>
      <h2 className='showcase-section-title mb-3 text-sm'>امکانات ملک</h2>
      <div className='grid grid-cols-4 gap-1.5 sm:gap-2'>
        {AMENITIES.map(({ key, label, icon: Icon }) => {
          const available = property[key];
          return (
            <div
              key={key}
              title={available ? undefined : `${label} ندارد`}
              className={cn(
                'flex flex-col items-center gap-1.5 rounded-xl border border-white/8 bg-white/[0.03] px-1 py-2 transition-all hover:border-gold-accent hover:bg-white/[0.06]',
                !available && 'opacity-40'
              )}
            >
              <Icon className='text-gold-primary size-4 sm:size-5' />
              <span className='text-showcase-muted text-center text-[0.66rem] font-semibold sm:text-[0.7rem]'>
                {label}
              </span>
              {!available && <span className='sr-only'>ندارد</span>}
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* ----------------------------------------------------------- action rows --- */

function ActionRow({
  icon,
  tone,
  label,
  onClick
}: {
  icon: React.ReactNode;
  tone: 'warning' | 'report';
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type='button'
      onClick={onClick}
      className={cn(
        'showcase-panel flex w-full cursor-pointer items-center gap-2 p-2.5 text-start text-xs font-semibold text-showcase-muted transition-all hover:border-gold-accent hover:bg-white/[0.05] hover:text-white sm:p-3',
        tone === 'warning' && 'hover:border-showcase-warning'
      )}
    >
      <span
        className={cn(
          'flex size-7 shrink-0 items-center justify-center rounded-lg border',
          tone === 'warning'
            ? 'border-showcase-warning/30 bg-showcase-warning/15 text-showcase-warning'
            : 'border-showcase-danger/30 bg-showcase-danger/15 text-showcase-danger'
        )}
      >
        {icon}
      </span>
      {label}
      <Icons.chevronLeft className='text-showcase-dim ms-auto size-4' />
    </button>
  );
}

/* ------------------------------------------------------------ description --- */

function DescriptionCard({ property, compact = false }: { property: PropertySummary; compact?: boolean }) {
  const description = property.description.trim();
  const [fullTextOpen, setFullTextOpen] = React.useState(false);

  return (
    <section className={cn('showcase-panel p-3 sm:p-4', compact && 'property-detail-description')}>
      <h2 className='showcase-section-title mb-2.5 text-sm'>توضیحات ملک</h2>
      {description ? (
        <>
          <p className={cn('text-[#cbd5e1] text-xs leading-7 whitespace-pre-line', compact && 'line-clamp-2')}>{description}</p>
          {compact && description.length > 140 && <Button variant='link' size='sm' className='h-auto px-0 pt-1 text-xs' onClick={() => setFullTextOpen(true)}>مشاهدهٔ متن کامل</Button>}
          <Modal title='توضیحات ملک' description='متن کامل توضیحات آگهی' isOpen={fullTextOpen} onClose={() => setFullTextOpen(false)}>
            <p className='max-h-[60dvh] overflow-y-auto whitespace-pre-line text-sm leading-7'>{description}</p>
          </Modal>
        </>
      ) : (
        <p className='text-showcase-dim text-xs leading-7'>
          برای این آگهی توضیحی ثبت نشده است. برای دریافت جزئیات کامل با مشاور تماس بگیرید.
        </p>
      )}
    </section>
  );
}

/* ---------------------------------------------------------------- advisor --- */

function AdvisorCard({
  property,
  onLeadCreated,
  compact = false
}: {
  property: PropertySummary;
  onLeadCreated?: () => void;
  compact?: boolean;
}) {
  const [pending, setPending] = React.useState(false);
  const [created, setCreated] = React.useState(false);
  const [messagePending, setMessagePending] = React.useState(false);
  const [guestPrompt, setGuestPrompt] = React.useState(false);
  const { user, isLoading: authLoading } = useAuthContext();
  const router = useRouter();

  const agency = property.agency_name?.trim() || '';
  const agent = property.agent_name?.trim() || '';
  const hasIdentity = Boolean(agency || agent);

  /**
   * Filing a lead is how this office actually contacts a seller, so the CTA
   * posts to the CRM rather than scraping a phone number out of a portal page.
   * The client is imported dynamically so the CRM bundle stays out of the
   * listing route's initial load, and the mutation is fired directly because a
   * hook cannot be called from inside a callback.
   */
  const fileLead = React.useCallback(async () => {
    if (!authLoading && !user) { setGuestPrompt(true); return; }
    setPending(true);
    try {
      const { createLead } = await import('@/features/crm/api/client');
      await createLead(property.id);
      setCreated(true);
      toast.success('این آگهی به کارتابل پیگیری اضافه شد.');
      onLeadCreated?.();
    } catch (error) {
      setCreated(false);
      toast.error(
        error instanceof Error ? error.message : 'ثبت پیگیری ناموفق بود.'
      );
    } finally {
      setPending(false);
    }
  }, [authLoading, user, property.id, onLeadCreated]);

  const openMessage = React.useCallback(async () => {
    if (!property.message_available || messagePending) return;
    if (!authLoading && !user) { setGuestPrompt(true); return; }
    setMessagePending(true);
    try {
      const { openPropertyConversation } = await import('@/features/chat/api/client');
      await openPropertyConversation(property.id);
      router.push('/dashboard/chat');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'بازکردن گفت‌وگو ممکن نشد.');
    } finally {
      setMessagePending(false);
    }
  }, [authLoading, user, messagePending, property.id, property.message_available, router]);

  return (
    <section className={cn('showcase-panel relative overflow-hidden border-gold-accent/35', compact && 'property-detail-advisor')}>
      <span
        aria-hidden
        className='absolute inset-x-0 top-0 h-[3px] bg-gradient-to-l from-transparent via-gold-primary to-transparent'
      />
      <div className='border-b border-dashed border-gold-primary/15 bg-gradient-to-b from-gold-accent/8 to-transparent px-3 py-3.5 text-center sm:px-4 sm:py-4'>
        <div className='mb-2.5 flex flex-wrap justify-center gap-1.5'>
          <Badge tone='source'>{SOURCE_LABELS[property.source]}</Badge>
          {SOURCE_TRUSTED[property.source] && <Badge tone='trusted'>ثبت مستقیم</Badge>}
        </div>

        <span className='text-gold-primary mx-auto mb-2 flex size-13 items-center justify-center rounded-full border-2 border-gold-accent bg-gradient-to-br from-gold-accent/20 to-gold-primary/10 text-xl font-extrabold shadow-[0_0_15px_rgb(229_168_123/0.2)] sm:size-16 sm:text-2xl'>
          <Icons.user className='size-6 sm:size-8' />
        </span>

        <p className='mb-1 text-sm font-extrabold text-white'>
          {agency || 'مشاور آگهی'}
        </p>
        <p className='text-showcase-muted text-[0.72rem]'>{agent || 'اطلاعات تماس مستقیم در دسترس نیست'}</p>

        {property.source_ref && (
          <p className='text-showcase-muted mt-2.5 inline-block rounded-full border border-white/8 bg-white/[0.04] px-2.5 py-1 text-[0.7rem]'>
            {`کد ملک: ${toPersianDigits(property.source_ref)}`}
          </p>
        )}
      </div>

      <div className='space-y-2 px-3 py-3.5 sm:px-4 sm:py-4'>
        {user ? (
          <Button className='w-full' disabled={pending} onClick={() => void fileLead()}>
            <Icons.phone className='size-4' />
            {pending ? 'در حال ثبت…' : created ? 'در پیگیری ثبت شد' : 'افزودن به پیگیری'}
          </Button>
        ) : (
          <Button className='w-full' onClick={() => setGuestPrompt(true)}>افزودن به پیگیری</Button>
        )}
        {user ? (
          <Button
            type='button'
            variant='outline'
            className='w-full justify-start gap-2 text-start'
            disabled={!property.message_available || messagePending}
            onClick={() => void openMessage()}
            aria-disabled={!property.message_available}
            title={property.message_unavailable_reason ?? 'پیام داخلی برای این آگهی در دسترس نیست.'}
          >
            <Icons.chat className='size-4 shrink-0' />
            {messagePending ? 'در حال بازکردن گفت‌وگو…' : 'ارسال پیام'}
          </Button>
        ) : property.message_available ? (
          <Button type='button' variant='outline' className='w-full justify-start gap-2' onClick={() => setGuestPrompt(true)}>
            <Icons.chat className='size-4 shrink-0' /> ارسال پیام
          </Button>
        ) : (
          <Button type='button' variant='outline' className='w-full justify-start gap-2' disabled title={property.message_unavailable_reason ?? undefined}>
            <Icons.chat className='size-4 shrink-0' /> ارسال پیام
          </Button>
        )}
        <p className='text-showcase-dim text-center text-[0.68rem] leading-6'>
          {hasIdentity
            ? 'ثبت پیگیری، این آگهی را به کارتابل شما اضافه می‌کند.'
            : 'این آگهی از پرتال گرفته شده و اطلاعات تماس آن هنوز تأیید نشده است.'}
        </p>
        <p role='note' className='text-showcase-dim text-center text-[0.65rem] leading-5'>
          {property.message_available ? 'گفت‌وگوی داخلی فقط برای آگهی‌های مستقیمِ دارای مالک معتبر در سامانه و با مجوز لازم فعال است.' : property.source === 'DIVAR' || property.source === 'DELTA' || property.source === 'SHEYPOOR' ? 'این آگهی از یک منبع خارجی جمع‌آوری شده و امکان گفت‌وگوی مستقیم در شکارچی برای آن فراهم نیست.' : property.message_unavailable_reason ?? 'پیام داخلی برای این آگهی در دسترس نیست.'}
        </p>
      </div>
      <GuestActionDialog open={guestPrompt} propertyId={property.id} onClose={() => setGuestPrompt(false)} />
    </section>
  );
}

/* ----------------------------------------------------------------- report --- */

function ReportDialog({
  propertyId,
  open,
  onClose
}: {
  propertyId: string;
  open: boolean;
  onClose: () => void;
}) {
  const report = useReportProperty();
  const [reason, setReason] = React.useState<ReportReason>('misleading');

  const submit = React.useCallback(() => {
    report.mutate(
      { propertyId, payload: { reason } },
      {
        onSuccess: () => {
          toast.success('گزارش شما ثبت شد. با تشکر از همکاری شما.');
          onClose();
        },
        onError: (mutationError: Error) => {
          toast.error(mutationError.message || 'ثبت گزارش ناموفق بود.');
        }
      }
    );
  }, [report, propertyId, reason, onClose]);

  return (
    <Modal
      title='گزارش اشکال در آگهی'
      description='اگر این آگهی مشکلی دارد (اطلاعات نادرست، تصاویر نامرتبط، اسپم و ...)، به ما اطلاع دهید تا بررسی کنیم.'
      isOpen={open}
      onClose={onClose}
    >
      <fieldset className='mb-5 flex flex-col gap-2'>
        <legend className='text-showcase-muted mb-1 text-xs font-semibold'>دلیل گزارش</legend>
        {(Object.keys(REPORT_REASON_LABELS) as ReportReason[]).map((value) => (
          <label
            key={value}
            className={cn(
              'flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-xs transition-colors',
              reason === value
                ? 'border-gold-accent bg-gold-accent/10 text-white'
                : 'border-white/8 text-showcase-muted hover:border-gold-accent/40'
            )}
          >
            <input
              type='radio'
              name='report-reason'
              className='accent-[#e5a87b]'
              checked={reason === value}
              onChange={() => setReason(value)}
            />
            {REPORT_REASON_LABELS[value]}
          </label>
        ))}
      </fieldset>

      <div className='flex gap-2'>
        <Button
          className='flex-1'
          disabled={report.isPending}
          onClick={submit}
        >
          {report.isPending && <Icons.spinner className='size-4 animate-spin' />}
          ارسال گزارش
        </Button>
        <Button variant='ghost' className='flex-1' onClick={onClose}>
          انصراف
        </Button>
      </div>
    </Modal>
  );
}
