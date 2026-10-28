"use client";

import * as React from "react";
import { Icons } from "@/components/icons";
import { Modal } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, toPersianDigits } from "@/lib/utils";
import { useNearbyPoi } from "../hooks";
import type { NearbyPoiItem } from "../types";

/**
 * "What is near this property" block: the five Overpass buckets the backend
 * groups amenities into, nearest first within each.
 *
 * This is a location-explainer, not a recommendation engine. Everything it shows
 * is an existing named place inside the query radius, so a broker can sanity-check
 * an address ("no transit within 2km") without leaving the listing. Distances are
 * rendered because the order is distance-based: seeing that the third pharmacy is
 * 1.4km away is the actual information.
 *
 * Every bucket key is always present in the response, so the five cards render in
 * a fixed order rather than reflowing as data lands. A bucket with no results
 * shows an explicit "nothing found" line -- an empty card would read as a loading
 * bug, and silently dropping it would hide that the search really did run.
 *
 * Styling stays on the rose-gold identity (cream border, gold icon wells):
 * five buckets share the same card chrome, differentiated by icon + heading.
 *
 * The 5-card grid is balanced on a 6-col track: row 1 holds three cards at
 * 2 cols each, row 2 splits into two equal 3-col halves, so no orphan gap is
 * left hanging. Cards stretch to equal row height (`h-full` + flex column)
 * with the empty state centred in the free space.
 */

/** Bucket key -> heading and glyph. Order matches `poi_service.BUCKETS`. */
const BUCKETS: ReadonlyArray<{
  key: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}> = [
  { key: "transport", label: "حمل و نقل عمومی", icon: Icons.poiTransport },
  { key: "shopping", label: "مراکز خرید", icon: Icons.poiShopping },
  { key: "education", label: "آموزشی", icon: Icons.poiEducation },
  { key: "healthcare", label: "درمانی و سلامت", icon: Icons.poiHealthcare },
  { key: "leisure", label: "تفریحی و ورزشی", icon: Icons.poiLeisure }
];

/**
 * Column spans that turn the 5 fixed buckets into a balanced layout.
 *
 * Row 1: three cards x 2 cols each. Row 2: cards 4-5 x 3 cols each, so the
 * last row is two equal halves instead of two thirds plus an orphan gap.
 * `sm` keeps 2-per-row; the mobile single column is untouched.
 */
const CARD_SPANS: ReadonlyArray<string> = [
  "sm:col-span-1 lg:col-span-2",
  "sm:col-span-1 lg:col-span-2",
  "sm:col-span-1 lg:col-span-2",
  "sm:col-span-1 lg:col-span-3",
  "sm:col-span-1 lg:col-span-3"
];

interface NearbyPoiBlockProps {
  propertyId: string;
  className?: string;
  /**
   * Render only the bucket grid (no outer panel/heading).
   *
   * The detail page embeds the grid inside its single merged «موقعیت مکانی»
   * section, so a second panel + heading would read as a duplicate location
   * block.
   */
  bare?: boolean;
  compact?: boolean;
}

export function NearbyPoiBlock({ propertyId, className, bare = false, compact = false }: NearbyPoiBlockProps) {
  const { data, isPending, isError } = useNearbyPoi(propertyId);

  // A listing without coordinates resolves with radius 0 and every bucket empty,
  // which the grid already renders honestly. No special case needed.
  const buckets = data?.buckets ?? {};
  const hasResults = BUCKETS.some(({ key }) => (buckets[key] ?? []).length > 0);

  if (!isPending && !isError && !hasResults) {
    return bare ? <span className='nearby-poi-empty hidden' aria-hidden /> : null;
  }

  const body = isPending ? (
    <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {BUCKETS.map(({ key }) => (
        <Skeleton key={key} className="h-28 rounded-xl" />
      ))}
    </div>
  ) : isError ? (
    <p className="text-muted-foreground py-4 text-center text-xs">
      امکانات نزدیک در این لحظه در دسترس نیست.
    </p>
  ) : (
    <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-6">
      {BUCKETS.map(({ key, label, icon: Icon }, i) => (
        <PoiCard
          key={key}
          label={label}
          icon={<Icon className="size-4" />}
          items={buckets[key] ?? []}
          radiusM={data?.radius_m ?? 0}
          spanClass={CARD_SPANS[i]}
          compact={compact}
        />
      ))}
    </div>
  );

  if (bare) return <div className={cn("min-w-0", className)}>{body}</div>;

  return (
    <section className={cn("showcase-panel min-w-0 overflow-hidden p-5", className)}>
      <h2 className="showcase-section-title mb-4 text-sm">امکانات نزدیک به این ملک</h2>

      {body}
    </section>
  );
}

function PoiCard({
  label,
  icon,
  items,
  radiusM,
  spanClass,
  compact
}: {
  label: string;
  icon: React.ReactNode;
  items: NearbyPoiItem[];
  radiusM: number;
  spanClass: string;
  compact: boolean;
}) {
  const [fullListOpen, setFullListOpen] = React.useState(false);
  const shownItems = compact ? items.slice(0, 1) : items;
  return (
    <div
      className={cn(
        "hover:border-gold-accent flex h-full min-w-0 flex-col rounded-xl border border-gold-primary/10 bg-white/[0.02] p-3.5 transition-all hover:-translate-y-0.5",
        spanClass
      )}
    >
      <div className="mb-2.5 flex items-center gap-2 border-b border-white/[0.06] pb-2">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-gold-accent/15 text-gold-primary">
          {icon}
        </span>
        <span className="text-xs font-bold text-white">{label}</span>
      </div>

      {items.length === 0 ? (
        <p className="text-showcase-dim flex flex-1 flex-col items-center justify-center py-4 text-center text-[0.7rem] leading-6">
          {radiusM > 0
            ? `موردی در شعاع ${toPersianDigits(radiusM.toLocaleString("en-US"))} متر یافت نشد`
            : "این ملک مختصات دقیق ندارد"}
        </p>
      ) : (
        <ul className="flex flex-1 flex-col gap-1.5">
           {shownItems.map((item) => (
            <li
              key={`${item.name}-${item.lat}-${item.lng}`}
              className="text-showcase-muted relative ps-3.5 text-[0.7rem] leading-6"
            >
              <span aria-hidden className="text-gold-accent absolute start-0 top-0 font-extrabold">
                •
              </span>
              {item.name}
              <span className="text-showcase-dim tabular-nums">
                {` — ${toPersianDigits(Math.round(item.distance_m).toLocaleString("en-US"))} متر`}
              </span>
            </li>
          ))}
        </ul>
      )}
      {compact && items.length > 1 && <button type='button' className='mt-1 text-start text-[0.58rem] font-medium text-gold-accent underline-offset-2 hover:underline' onClick={() => setFullListOpen(true)}>
        {`مشاهدهٔ ${toPersianDigits((items.length - 1).toLocaleString("en-US"))} مورد دیگر`}
      </button>}
      <Modal title={label} description='فهرست کامل امکانات نزدیک ثبت‌شده برای این موقعیت' isOpen={fullListOpen} onClose={() => setFullListOpen(false)}>
        <ul className='max-h-[60dvh] space-y-2 overflow-y-auto text-sm'>
          {items.map((item) => <li key={`${item.name}-${item.lat}-${item.lng}`} className='flex items-center justify-between gap-3 border-b pb-2'>
            <span>{item.name}</span>
            <span className='shrink-0 text-muted-foreground'>{`${toPersianDigits(Math.round(item.distance_m).toLocaleString("en-US"))} متر`}</span>
          </li>)}
        </ul>
      </Modal>
    </div>
  );
}
