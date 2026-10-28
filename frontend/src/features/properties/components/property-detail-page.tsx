'use client';

import * as React from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import { Icons } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { PropertyMap } from '@/features/map/components/property-map';
import { cn, formatToman, toPersianDigits } from '@/lib/utils';
import { HeroGallery } from './hero-gallery';
import { NearbyPoiBlock } from './nearby-poi-block';
import { PropertyShowcaseSidebar } from './property-showcase-sidebar';
import { VisitSchedulerWidget } from './visit-scheduler-widget';
import { usePriceHistory, useProperty, usePropertyMedia, useRevalueProperty } from '../hooks';
import type { ValuationStatus } from '../types';
import {
  DEAL_TYPE_LABELS,
  PRICE_SOURCE_LABELS,
  PROPERTY_STATUS_LABELS,
  PROPERTY_TYPE_LABELS,
  formatDeviation
} from '../utils/labels';

/**
 * One listing, in the showcase treatment: a wide media column (gallery, map,
 * nearby amenities) beside a sticky financial/legal/contact column.
 *
 * The gallery leads because it is what a broker looks at before the numbers, and
 * the two columns are deliberately unequal -- 1fr against a fixed 400px sidebar
 * that sticks once the media column starts out-scrolling it, so the price and the
 * contact action stay reachable while the photos are being flicked through.
 *
 * Three things this page will not do, each because the data to support them does
 * not exist on this node: show an advisor phone number, claim a deed is verified,
 * or print a valuation percentage. See `property-showcase-sidebar` for the
 * detail, and `hero-gallery` for why the thumbnail rail stops at four.
 */

/** Map pin colour follows the engine's verdict, same as the card badges. */
function mapToneFor(status: ValuationStatus): 'bargain' | 'fair' | 'overpriced' {
  if (status === 'BARGAIN') return 'bargain';
  if (status === 'OVERPRICED') return 'overpriced';
  return 'fair';
}

export default function PropertyDetailPage({ propertyId }: { propertyId: string }) {
  const { data: property, isPending, isError, error } = useProperty(propertyId);
  const { data: media, isPending: mediaPending } = usePropertyMedia(propertyId);
  const { data: priceHistory, isPending: historyPending } = usePriceHistory(propertyId);
  const revalue = useRevalueProperty();

  if (isPending) {
    return (
      <div className='property-detail-viewport mk-detail-standard showcase-shell grid min-w-0 overflow-x-clip gap-2 rounded-2xl p-2 sm:p-3 lg:grid-cols-[1fr_320px]'>
        <Skeleton className='aspect-[3/2] w-full rounded-[14px]' />
        <div className='hidden flex-col gap-2 lg:flex'>
          <Skeleton className='h-28 w-full rounded-[14px]' />
          <Skeleton className='h-24 w-full rounded-[14px]' />
          <Skeleton className='h-32 w-full rounded-[14px]' />
        </div>
      </div>
    );
  }

  if (isError || !property) {
    return (
      <Card>
        <CardContent className='flex flex-col items-center gap-2 py-10 text-center'>
          <Icons.warning className='text-destructive size-6' />
          <p className='text-sm font-medium'>{error?.message ?? 'ملک یافت نشد.'}</p>
        </CardContent>
      </Card>
    );
  }

  const location = [property.neighborhood, property.city].filter(Boolean).join('، ');
  const galleryTitle = property.title || `${property.property_type} در ${location}`;
  const hasPin = property.latitude != null && property.longitude != null;

  return (
    <div className='property-detail-viewport mk-detail-standard showcase-shell property-detail-premium min-h-0 min-w-0 overflow-x-clip rounded-2xl p-2 sm:p-3'>
      <div className='property-detail-toolbar mb-2 flex min-w-0 flex-wrap items-center justify-between gap-2'>
        <nav className='text-showcase-dim flex flex-wrap items-center gap-1.5 text-[0.68rem]'>
          <Link href='/dashboard/properties' className='hover:text-gold-primary transition-colors'>
            فایل‌ها
          </Link>
          <span aria-hidden className='text-gold-primary/30'>
            ›
          </span>
          <span className='text-showcase-muted line-clamp-1'>{galleryTitle}</span>
        </nav>

        <div className='flex items-center gap-2'>
          <Button
            variant='outline'
            size='sm'
            className='border-gold-primary/25 text-gold-primary hover:bg-gold-accent hover:text-showcase'
            disabled={revalue.isPending}
            onClick={() => revalue.mutate(property.id)}
          >
            <Icons.adjustments className='size-4' />
            ارزش‌گذاری مجدد
          </Button>
          <Button
            variant='ghost'
            size='sm'
            className='text-showcase-muted hover:text-gold-primary'
            render={<Link href='/dashboard/properties' />}
          >
            <Icons.chevronRight className='size-4' />
            بازگشت
          </Button>
        </div>
      </div>

      <section className='property-detail-summary showcase-panel mb-3 grid min-w-0 gap-3 p-3 sm:mb-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:p-5'>
        <div className='min-w-0'>
          <p className='text-showcase-dim mb-1 text-xs font-medium'>
            {location || 'موقعیت در آگهی ثبت نشده است'}
          </p>
          <h1 className='text-showcase-text text-lg font-bold leading-8 sm:text-2xl'>{galleryTitle}</h1>
          <div className='mt-2 flex flex-wrap gap-2 text-xs text-showcase-muted'>
            <span className='rounded-full border border-border px-2.5 py-1'>{DEAL_TYPE_LABELS[property.deal_type]}</span>
            <span className='rounded-full border border-border px-2.5 py-1'>{PROPERTY_TYPE_LABELS[property.property_type]}</span>
            <span className='rounded-full border border-border px-2.5 py-1'>{PROPERTY_STATUS_LABELS[property.status]}</span>
            <span className='rounded-full border border-border px-2.5 py-1'>شناسه {toPersianDigits(property.id.slice(0, 8))}</span>
          </div>
        </div>
        <div className='min-w-0 border-t border-border pt-3 text-start sm:border-t-0 sm:border-s sm:pt-0 sm:ps-5'>
          <p className='text-showcase-dim mb-1 text-xs'>قیمت آگهی</p>
          <p className='text-gold-primary text-xl font-extrabold tabular-nums sm:text-2xl'>
            {property.deal_type === 'SALE'
              ? (property.total_price == null ? 'قیمت ثبت نشده' : formatToman(property.total_price))
              : property.deal_type === 'FULL_MORTGAGE'
                ? `رهن کامل ${property.deposit_amount == null ? 'ثبت نشده' : formatToman(property.deposit_amount)}`
                : `رهن ${property.deposit_amount == null ? 'ثبت نشده' : formatToman(property.deposit_amount)} · اجاره ${property.monthly_rent == null ? 'ثبت نشده' : formatToman(property.monthly_rent)}`}
          </p>
        </div>
        <div className='grid grid-cols-2 gap-2 border-t border-border pt-3 sm:col-span-2 sm:grid-cols-4'>
          <SummaryFact icon={<Icons.statArea className='size-4' />} label='متراژ' value={property.area ? `${toPersianDigits(property.area.toLocaleString('en-US'))} متر` : null} />
          <SummaryFact icon={<Icons.statBed className='size-4' />} label='اتاق‌خواب' value={property.rooms == null ? null : toPersianDigits(String(property.rooms))} />
          <SummaryFact icon={<Icons.building className='size-4' />} label='طبقه' value={property.floor == null ? null : toPersianDigits(String(property.floor))} />
          <SummaryFact icon={<Icons.calendar className='size-4' />} label='سال ساخت' value={property.year_built == null ? null : toPersianDigits(String(property.year_built))} />
        </div>
      </section>

      <div className='property-detail-grid grid min-w-0 grid-cols-1 items-start gap-3'>
        {/* ------------------------------------------------- media column --- */}
        <div className='property-detail-media flex min-w-0 flex-col gap-2'>
          <HeroGallery
            className='property-detail-gallery'
            compact
            images={media?.items ?? []}
            title={galleryTitle}
            placeholderLabel='تصویری برای این ملک ثبت نشده است'
            loading={mediaPending}
          />

          <section className='showcase-panel property-detail-location min-w-0 overflow-hidden'>
            <div className='property-detail-location-grid min-w-0'>
              <div className='property-detail-map-panel min-w-0 overflow-hidden'>
                {hasPin ? (
                  <>
                <PropertyMap
                  pins={[
                    {
                      id: property.id,
                      lat: property.latitude as number,
                      lng: property.longitude as number,
                      label: [property.neighborhood, property.city].filter(Boolean).join('، '),
                      tone: mapToneFor(property.valuation_status),
                      privacyRadiusM: property.privacy_radius_m,
                      privacyAccent: '#e5a87b'
                    }
                  ]}
                  zoom={15}
                  height={150}
                  className='!rounded-none !border-0'
                />
                <p className='property-detail-map-caption text-muted-foreground flex flex-wrap items-center justify-center gap-1.5 border-t border-border bg-muted/60 px-3 py-2 text-center text-[0.72rem] font-semibold'>
                  <Icons.mapPin className='text-gold-accent size-4 shrink-0' />
                  موقعیت تقریبی/امنیتی ملک روی نقشه
                  <span className='text-showcase-dim font-normal'>
                    {` — شعاع ${toPersianDigits(property.privacy_radius_m.toLocaleString('en-US'))} متر`}
                  </span>
                </p>
                  </>
                ) : (
              <p className='text-muted-foreground px-3 py-4 text-center text-xs'>
                این آگهی مختصات دقیقی ندارد، بنابراین روی نقشه نمایش داده نمی‌شود.
              </p>
                )}
              </div>
              {hasPin && <div className='property-detail-poi-panel min-w-0 border-s border-border px-2 py-2'>
                <h3 className='showcase-section-title mb-1.5 text-[0.68rem]'>امکانات نزدیک</h3>
                  <NearbyPoiBlock propertyId={property.id} bare compact className='property-detail-poi-compact' />
              </div>}
            </div>
          </section>

          <PriceHistoryCard entries={priceHistory} loading={historyPending} compact />
        </div>

        {/* ----------------------------------------------- compact facts column --- */}
        <div className='property-detail-facts min-w-0'>
          <PropertyShowcaseSidebar
            property={property}
            compact
            onLeadCreated={() => toast.success('این آگهی به کارتابل پیگیری اضافه شد.')}
          />
        </div>

        <VisitSchedulerWidget propertyId={property.id} compact />
      </div>
    </div>
  );
}

function SummaryFact({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | null }) {
  return (
    <div className='flex min-w-0 items-center gap-2 rounded-xl border border-border bg-muted/30 px-3 py-2'>
      <span className='text-gold-primary shrink-0'>{icon}</span>
      <span className='text-showcase-dim shrink-0 text-xs'>{label}</span>
      <span className='text-showcase-text ms-auto truncate text-sm font-semibold'>{value ?? '—'}</span>
    </div>
  );
}

/**
 * Price timeline.
 *
 * Kept in the media column rather than the sidebar because it is a scroll-length
 * table, not a spec: it is what a supervisor reads once the decision is close.
 */
function PriceHistoryCard({
  entries,
  loading,
  compact = false
}: {
  entries: ReturnType<typeof usePriceHistory>['data'];
  loading: boolean;
  compact?: boolean;
}) {
  return (
    <section className={cn('showcase-panel min-w-0 p-3 sm:p-4', compact && 'property-detail-history')}>
      <h2 className='showcase-section-title mb-2.5 text-sm'>تاریخچه قیمت</h2>
      {loading ? (
        <Skeleton className='h-20 w-full' />
      ) : !entries || entries.length === 0 ? (
        <p className='text-muted-foreground py-5 text-center text-xs'>
          تا این لحظه تنها یک قیمت برای این فایل مشاهده شده است.
        </p>
      ) : compact && entries.length > 2 ? (
        <>
          <PriceHistoryTable entries={entries.slice(0, 2)} />
          <details className='mt-1 border-t pt-1 text-xs'>
            <summary className='cursor-pointer py-1 text-muted-foreground'>مشاهدهٔ {toPersianDigits(String(entries.length - 2))} سابقهٔ دیگر</summary>
            <div className='max-h-40 overflow-y-auto'>
              <PriceHistoryTable entries={entries.slice(2)} />
            </div>
          </details>
        </>
      ) : (
        <PriceHistoryTable entries={entries} />
      )}
    </section>
  );
}

function PriceHistoryTable({ entries }: { entries: NonNullable<ReturnType<typeof usePriceHistory>['data']> }) {
  return (
    <Table className='text-xs sm:text-sm [&_td]:py-2 [&_th]:h-8'>
      <TableHeader>
        <TableRow>
          <TableHead className='ps-0'>قیمت</TableHead>
          <TableHead>تغییر</TableHead>
          <TableHead className='hidden text-start md:table-cell'>منبع</TableHead>
          <TableHead className='text-start'>تاریخ</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries.map((entry) => {
          const dropped = entry.price_difference < 0;
          return (
            <TableRow key={entry.id}>
              <TableCell className='ps-0 font-medium tabular-nums'>{formatToman(entry.new_price)}</TableCell>
              <TableCell className={cn('font-medium tabular-nums', dropped ? 'text-destructive' : 'text-muted-foreground')}>
                {formatDeviation(entry.change_percentage)}
              </TableCell>
              <TableCell className='hidden text-muted-foreground md:table-cell'>
                {PRICE_SOURCE_LABELS[entry.source]}{entry.source_ref ? ` — ${entry.source_ref}` : ''}
              </TableCell>
              <TableCell className='text-muted-foreground text-start'>{new Date(entry.recorded_at).toLocaleDateString('fa-IR')}</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
