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
import { PRICE_SOURCE_LABELS, formatDeviation } from '../utils/labels';

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
      <div className='mk-detail-standard showcase-shell grid min-w-0 overflow-x-clip gap-2 rounded-2xl p-2 sm:p-3 lg:grid-cols-[1fr_320px]'>
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
  const hasPin = property.latitude !== null && property.longitude !== null;

return (
    <div className='mk-detail-standard showcase-shell min-h-full min-w-0 overflow-x-clip rounded-2xl p-3 sm:p-5'>
      <div className='mb-3 flex min-w-0 flex-wrap items-center justify-between gap-3'>
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

      <div className='grid min-w-0 grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,1fr)_340px]'>
        {/* ------------------------------------------------- media column --- */}
        <div className='flex min-w-0 flex-col gap-3'>
          <HeroGallery
            images={media?.items ?? []}
            title={galleryTitle}
            placeholderLabel='تصویری برای این ملک ثبت نشده است'
            loading={mediaPending}
          />

          <section className='showcase-panel min-w-0 overflow-hidden'>
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
                  height={260}
                  className='!rounded-none !border-0'
                />
                <p className='text-muted-foreground flex flex-wrap items-center justify-center gap-1.5 border-t border-border bg-muted/60 px-3 py-2.5 text-center text-[0.78rem] font-semibold'>
                  <Icons.mapPin className='text-gold-accent size-4 shrink-0' />
                  موقعیت تقریبی/امنیتی ملک روی نقشه
                  <span className='text-showcase-dim font-normal'>
                    {` — شعاع ${toPersianDigits(property.privacy_radius_m.toLocaleString('en-US'))} متر`}
                  </span>
                </p>
              </>
            ) : (
              <p className='text-muted-foreground px-4 py-6 text-center text-xs'>
                این آگهی مختصات دقیقی ندارد، بنابراین روی نقشه نمایش داده نمی‌شود.
              </p>
            )}
            {/* Nearby amenities belong to the same location section: a second
                panel + heading below the map reads as a duplicate « site » block. */}
            {hasPin && (
              <div className='border-t border-border px-3 py-3 sm:px-4 sm:py-3.5'>
                <h3 className='showcase-section-title mb-2.5 text-xs'>امکانات نزدیک به این ملک</h3>
                <NearbyPoiBlock propertyId={property.id} bare />
              </div>
            )}
          </section>

          <PriceHistoryCard entries={priceHistory} loading={historyPending} />
        </div>

        {/* ----------------------------------------------- sticky column --- */}
        <aside className='flex min-w-0 max-w-full flex-col gap-3 lg:sticky lg:top-[76px]'>
          <PropertyShowcaseSidebar
            property={property}
            onLeadCreated={() => toast.success('این آگهی به کارتابل پیگیری اضافه شد.')}
          />
          {/* The scheduler sits under the contact action: it is the next thing
              an advisor does after reading the sidebar, and it must be
              reachable without scrolling back up the gallery. */}
          <VisitSchedulerWidget propertyId={property.id} />
        </aside>
      </div>
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
  loading
}: {
  entries: ReturnType<typeof usePriceHistory>['data'];
  loading: boolean;
}) {
  return (
    <section className='showcase-panel min-w-0 p-3 sm:p-4'>
      <h2 className='showcase-section-title mb-2.5 text-sm'>تاریخچه قیمت</h2>
      {loading ? (
        <Skeleton className='h-20 w-full' />
      ) : !entries || entries.length === 0 ? (
        <p className='text-muted-foreground py-5 text-center text-xs'>
          تا این لحظه تنها یک قیمت برای این فایل مشاهده شده است.
        </p>
      ) : (
        /* The source column is the first thing a narrow screen drops: the
           reference is provenance, not a decision input, and the price and
           its change carry the row. The container scrolls rather than
           squashing the figures below a legible width. */
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
                  <TableCell className='ps-0 font-medium tabular-nums'>
                    {formatToman(entry.new_price)}
                  </TableCell>
                  <TableCell
                    className={cn(
                      'font-medium tabular-nums',
                      dropped ? 'text-destructive' : 'text-muted-foreground'
                    )}
                  >
                    {formatDeviation(entry.change_percentage)}
                  </TableCell>
                  <TableCell className='hidden text-muted-foreground md:table-cell'>
                    {PRICE_SOURCE_LABELS[entry.source]}
                    {entry.source_ref ? ` — ${entry.source_ref}` : ''}
                  </TableCell>
                  <TableCell className='text-muted-foreground text-start'>
                    {new Date(entry.recorded_at).toLocaleDateString('fa-IR')}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
