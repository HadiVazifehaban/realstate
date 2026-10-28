"use client";

import * as React from 'react';
import { Icons } from '@/components/icons';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn, toPersianDigits } from '@/lib/utils';
import { mediaUrl } from '@/lib/media-url';
import type { PropertyMediaItem } from '../types';

/**
 * Listing hero gallery: photos, floor plans and videos behind one tab strip.
 *
 * Mirrors the layout advisors already read on Delta and Sheypoor -- a big image
 * with a thumbnail row beneath it -- because a broker scanning inventory expects
 * to flick through photos without a page load.
 *
 * No carousel dependency: the selection is plain React state, so there is no
 * animation instance to dispose when the advisor moves between listings.
 *
 * The rail is a fixed four-column grid rather than a horizontal scroller. It
 * caps at four on purpose: a portal gallery previews the first four and defers
 * the rest, and a scroller full of 9 photos hides the fact that more exist.
 *
 * Tabs, not a filter: a plan tab that vanishes on a listing with no plans
 * leaves a dead strip behind, so an empty kind renders its own plate saying the
 * node has nothing of that kind -- the advisor learns the difference between
 * "no photos" and "not loaded yet".
 */

interface HeroGalleryProps {
  images: PropertyMediaItem[];
  /** Alt text for the hero; usually the listing title. */
  title: string;
  /** Plate shown when the listing has no servable image at all. */
  placeholderLabel: string;
  loading?: boolean;
  className?: string;
  /** Constrained stage for the dashboard's viewport-sized detail layout. */
  compact?: boolean;
}

/** How many thumbnails the strip previews before deferring the rest. */
const THUMB_SLOTS = 4;

type MediaKind = 'IMAGE' | 'FLOOR_PLAN' | 'VIDEO';

/** Tab order is reading order: photos, then the plan, then the walkthrough. */
const TABS: { kind: MediaKind; label: string }[] = [
  { kind: 'IMAGE', label: 'عکس‌ها' },
  { kind: 'FLOOR_PLAN', label: 'پلان' },
  { kind: 'VIDEO', label: 'ویدیو' }
];

/** Per-kind plate so an empty plan tab reads as "no plan", not "broken". */
const EMPTY_LABELS: Record<MediaKind, string> = {
  IMAGE: 'تصویری برای این ملک ثبت نشده است',
  FLOOR_PLAN: 'پلانی برای این ملک ثبت نشده است',
  VIDEO: 'ویدیویی برای این ملک ثبت نشده است'
};

export function HeroGallery({
  images,
  title,
  placeholderLabel,
  loading = false,
  className,
  compact = false
}: HeroGalleryProps) {
  const byKind = React.useMemo(() => {
    const map: Record<MediaKind, string[]> = { IMAGE: [], FLOOR_PLAN: [], VIDEO: [] };
    for (const image of images) {
      if (map[image.media_type]) map[image.media_type].push(mediaUrl(image.url));
    }
    return map;
  }, [images]);

  // The first tab that actually has something wins; without this a listing with
  // plans but no photos would open on an empty photo tab.
  const firstFilled = TABS.find((tab) => byKind[tab.kind].length > 0)?.kind ?? 'IMAGE';

  if (loading) {
    return <Skeleton className={cn('h-[280px] w-full rounded-[14px] sm:h-[340px] lg:h-[380px]', compact && 'property-detail-gallery-skeleton', className)} />;
  }

  if (!TABS.some((tab) => byKind[tab.kind].length > 0)) {
    return (
      <div
        className={cn(
          'showcase-panel text-showcase-muted flex h-[280px] w-full items-center justify-center font-medium tracking-wide sm:h-[340px] lg:h-[380px]',
          compact && 'property-detail-gallery-empty',
          className
        )}
      >
        {placeholderLabel}
      </div>
    );
  }

  return (
    <div className={cn('showcase-panel min-w-0 overflow-hidden', className)}>
      <Tabs defaultValue={firstFilled}>
        <TabsList variant='line' className='bg-showcase/90 w-full px-2.5 pt-2.5'>
          {TABS.map((tab) => (
            <TabsTrigger key={tab.kind} value={tab.kind}>
              {tab.label}
              {byKind[tab.kind].length > 0 && (
                <span className='text-gold-accent tabular-nums'>
                  {toPersianDigits(byKind[tab.kind].length.toLocaleString('en-US'))}
                </span>
              )}
            </TabsTrigger>
          ))}
        </TabsList>

        {TABS.map((tab) => (
          <TabsContent key={tab.kind} value={tab.kind} className='p-2.5'>
            <MediaStage kind={tab.kind} urls={byKind[tab.kind]} title={title} compact={compact} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}

/**
 * One stage of one tab: a big viewer over a four-up rail.
 *
 * Plans keep `object-contain` -- a plan is never cropped, the dimensions on it
 * are the point -- while photos fill the frame. Videos render as a native
 * `<video controls>`: the node hands over arbitrary CDN URLs, and a plain
 * element is the only thing that plays them without pulling in a player bundle.
 */
function MediaStage({
  kind,
  urls,
  title,
  compact
}: {
  kind: MediaKind;
  urls: string[];
  title: string;
  compact: boolean;
}) {
  const [active, setActive] = React.useState(0);
  const [viewerOpen, setViewerOpen] = React.useState(false);

  // A new listing can have fewer items than the previous one; without this the
  // viewer would keep pointing past the end of the rail.
  React.useEffect(() => {
    setActive((current) => (current < urls.length ? current : 0));
  }, [urls.length]);

  const share = React.useCallback(async () => {
    const url = typeof window === 'undefined' ? '' : window.location.href;
    if (navigator.share) {
      await navigator.share({ title, url }).catch(() => undefined);
      return;
    }
    await navigator.clipboard?.writeText(url);
  }, [title]);

  const step = React.useCallback(
    (delta: number) => {
      setActive((current) => (current + delta + urls.length) % urls.length);
    },
    [urls.length]
  );

  React.useEffect(() => {
    if (!viewerOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setViewerOpen(false);
      if (event.key === 'ArrowLeft') step(1);
      if (event.key === 'ArrowRight') step(-1);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [viewerOpen, step]);

  if (urls.length === 0) {
    return (
      <div className='text-showcase-muted flex aspect-[3/2] w-full items-center justify-center rounded-[14px] bg-showcase-surface-deep text-xs font-medium'>
        {EMPTY_LABELS[kind]}
      </div>
    );
  }

  const current = Math.min(active, urls.length - 1);
  const thumbs = urls.slice(0, THUMB_SLOTS);
  const noun = kind === 'IMAGE' ? 'تصویر' : kind === 'FLOOR_PLAN' ? 'پلان' : 'ویدیو';

  return (
    <>
      <div className={cn('group bg-showcase-surface-deep relative h-[280px] overflow-hidden rounded-[14px] sm:h-[340px] lg:h-[380px]', compact && 'property-detail-gallery-stage')}>
        {kind === 'VIDEO' ? (
          <video
            key={urls[current]}
            src={urls[current]}
            controls
            playsInline
            className='size-full bg-black object-contain'
          />
        ) : (
          <>
            {/* Plain <img>: these are arbitrary CDN/MLS URLs with unknown
                dimensions, which next/image cannot optimise without a loader. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              key={urls[current]}
              src={urls[current]}
              alt={title}
              className={cn(
                'size-full transition-transform duration-500 group-hover:scale-[1.03]',
                kind === 'FLOOR_PLAN' ? 'object-contain' : 'object-cover'
              )}
            />
          </>
        )}

        {urls.length > 1 && kind !== 'VIDEO' && (
          <>
            {/* In RTL the inline start is the right edge, so "previous" sits on
                the right and its chevron points right, matching reading order. */}
            <button
              type='button'
              className='showcase-circle-button absolute start-3 top-1/2 -translate-y-1/2'
              aria-label={`${noun} قبلی`}
              onClick={() => step(-1)}
            >
              <Icons.chevronRight className='size-4' />
            </button>
            <button
              type='button'
              className='showcase-circle-button absolute end-3 top-1/2 -translate-y-1/2'
              aria-label={`${noun} بعدی`}
              onClick={() => step(1)}
            >
              <Icons.chevronLeft className='size-4' />
            </button>
          </>
        )}

        {kind === 'IMAGE' && (
          <div className='absolute end-3 top-3 flex items-center gap-2'>
            <button
              type='button'
              className='showcase-circle-button'
              aria-label='ذخیره در علاقه‌مندی‌ها'
              disabled
              aria-disabled='true'
              title='ذخیرهٔ علاقه‌مندی در این سامانه هنوز در دسترس نیست.'
            >
              <Icons.exclusive className='size-4' />
            </button>
            <button
              type='button'
              className='showcase-circle-button'
              aria-label='اشتراک‌گذاری'
              onClick={() => void share()}
            >
              <Icons.share className='size-4' />
            </button>
            <button
              type='button'
              className='showcase-circle-button'
              aria-label='نمایش تمام‌صفحه تصویر'
              onClick={() => setViewerOpen(true)}
            >
              <Icons.media className='size-4' />
            </button>
          </div>
        )}

        {urls.length > 1 && (
          <span className='text-gold-primary absolute bottom-3 start-3 rounded-full border border-gold-accent/40 bg-showcase/85 px-3 py-1 text-xs font-semibold tabular-nums backdrop-blur-md'>
            {`${toPersianDigits((current + 1).toLocaleString('en-US'))} / ${toPersianDigits(urls.length.toLocaleString('en-US'))}`}
          </span>
        )}
      </div>

      {viewerOpen && kind === 'IMAGE' && (
        <div
          className='fixed inset-0 z-[100] flex items-center justify-center bg-black/95 p-3 sm:p-8'
          role='dialog'
          aria-modal='true'
          aria-label='گالری تمام‌صفحه'
          onClick={() => setViewerOpen(false)}
        >
          <button
            type='button'
            className='absolute end-4 top-4 z-10 rounded-full border border-white/25 bg-black/40 p-2 text-white hover:bg-white/15'
            aria-label='بستن گالری'
            onClick={() => setViewerOpen(false)}
          >
            <Icons.close className='size-5' />
          </button>
          {urls.length > 1 && <button type='button' className='showcase-circle-button absolute end-4 top-1/2 z-10 -translate-y-1/2' aria-label='تصویر قبلی' onClick={(event) => { event.stopPropagation(); step(-1); }}><Icons.chevronRight className='size-5' /></button>}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={urls[current]} alt={title} className='max-h-full max-w-full object-contain' onClick={(event) => event.stopPropagation()} />
          {urls.length > 1 && <button type='button' className='showcase-circle-button absolute start-4 top-1/2 z-10 -translate-y-1/2' aria-label='تصویر بعدی' onClick={(event) => { event.stopPropagation(); step(1); }}><Icons.chevronLeft className='size-5' /></button>}
          <div className='absolute inset-x-0 bottom-0 flex justify-center gap-2 overflow-x-auto bg-gradient-to-t from-black/75 to-transparent px-12 pb-3 pt-10'>
            {urls.map((url, index) => (
              <button
                key={`${url}-${index}`}
                type='button'
                aria-label={`نمایش تصویر ${toPersianDigits(String(index + 1))}`}
                aria-current={index === current}
                onClick={(event) => { event.stopPropagation(); setActive(index); }}
                className={`h-12 w-16 shrink-0 overflow-hidden rounded-md border-2 ${index === current ? 'border-[#c78b5c]' : 'border-white/30 opacity-70'}`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={url} alt='' loading='lazy' className='size-full object-cover' />
              </button>
            ))}
          </div>
          <span className='absolute bottom-4 rounded-full bg-black/60 px-3 py-1 text-sm text-white' aria-live='polite'>
            {`${toPersianDigits((current + 1).toLocaleString('en-US'))} / ${toPersianDigits(urls.length.toLocaleString('en-US'))}`}
          </span>
        </div>
      )}

      {urls.length > 1 && (
        <div className={cn('mt-2 grid grid-cols-4 gap-1.5 sm:gap-2', compact && 'property-detail-gallery-thumbs')} aria-label={`${noun}های آگهی`}>
          {thumbs.map((url, index) => (
            <button
              key={url}
              type='button'
              aria-current={index === current}
              aria-label={`${noun} ${toPersianDigits((index + 1).toLocaleString('en-US'))}`}
              onClick={() => setActive(index)}
              className={cn(
                'focus-visible:ring-ring aspect-[3/2] overflow-hidden rounded-lg border-2 transition-all',
                index === current
                  ? 'border-gold-accent shadow-[0_0_10px_rgb(229_168_123/0.3)]'
                  : 'border-transparent opacity-60 hover:border-gold-accent hover:opacity-100'
              )}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={url} alt='' loading='lazy' className='size-full object-cover' />
            </button>
          ))}
        </div>
      )}
    </>
  );
}
