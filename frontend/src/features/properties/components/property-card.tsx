"use client";

import Link from "next/link";
import * as React from "react";
import { motion } from "motion/react";
import { Icons } from "@/components/icons";
import { cn, formatPricePerMeter, formatToman, toPersianDigits } from "@/lib/utils";
import { mediaUrl } from '@/lib/media-url';
import type { PropertySummary } from "../types";
import {
  DEAL_TYPE_LABELS,
  PROPERTY_TYPE_LABELS,
  SOURCE_LABELS,
  SOURCE_SHORT_LABELS,
  VALUATION_LABELS,
  formatBuildingAge
} from "../utils/labels";
import { comparablePriceOf, marketVerdict } from "../utils/market";

/**
 * Ultra-luxury listing card for the Shekarchi buy/rent showcase rails.
 * Fixed dark-glass treatment (obsidian + champagne rose-gold), independent
 * of the dashboard theme. 4:3 thumbnail, source/type badges over the photo,
 * a 2x2 spec grid (icon + label on one side, value on the other), then the
 * price HUD — hover lift -4px + image scale 1.05, motion entrance staggered
 * by index.
 * No `visit_date`: a listing has no schedule; appointments live on the CRM.
 */

export type ShowcaseVariant = "buy" | "rent";

interface PropertyCardProps {
  property: PropertySummary;
  variant: ShowcaseVariant;
  index?: number;
  className?: string;
  /**
   * The market benchmark this listing is judged against, in the unit the
   * listing itself is quoted in — price per square metre for a sale, deposit
   * for a lease.
   *
   * The page hands it in from the same aggregation «تحلیل بازار» maps, so every
   * card in the grid can mark that figure against the market it would be priced
   * on. Optional on purpose: the showcase rails render a curated selection and
   * fetch no market feed, so their cards carry no marks rather than a
   * comparison they cannot back.
   */
  marketMedian?: number | null;
  /**
   * An overlay action on the thumbnail, for working the listing from where it
   * was found rather than navigating away from it.
   *
   * Rendered *after* -- and so on top of -- the card's ``<Link>``: a button
   * nested inside that anchor would be invalid HTML, and the click would
   * follow the link instead. Optional because the showcase rails are curated
   * surfaces that only read a listing; the office feed passes the add-to-lead
   * button here.
   */
  leadAction?: React.ReactNode;
}

const ENTER_DELAY_STEP = 0.045;
const ENTER_DELAY_CAP = 0.45;

export function PropertyCard({
  property,
  variant,
  index = 0,
  className,
  marketMedian,
  leadAction
}: PropertyCardProps) {
  const location = [property.neighborhood, property.city].filter(Boolean).join("، ");
  const age = formatBuildingAge(property.year_built);
  const isBargain = property.valuation_status === "BARGAIN";
  const isExclusive =
    property.source === "INTERNAL_AGENCY" || property.source === "INTERNAL_USER";
  const delay = Math.min(index * ENTER_DELAY_STEP, ENTER_DELAY_CAP);

  return (
    <motion.article
      initial={{ opacity: 0, y: 22 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.55, delay, ease: [0.22, 1, 0.36, 1] }}
      className={cn("lux-card group relative flex h-full min-w-0 flex-col overflow-hidden", className)}
    >
      {/* `flex-1` rather than `h-full`: the article is a flex column whose
          height comes from the grid cell, so `h-full` here would claim the whole
          of it and leave no room for an action strip below — the card would then
          grow past its row. Sharing the space keeps the price HUD pinned to the
          link's lower edge (`mt-auto` inside it) and the strip beneath it. */}
      <Link
        href={`/dashboard/properties/${property.id}`}
        aria-label={property.title || PROPERTY_TYPE_LABELS[property.property_type]}
        className="flex min-h-0 flex-1 flex-col rounded-[inherit] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gold-accent"
      >
        <div className="relative aspect-4/3 w-full shrink-0 overflow-hidden">
          <CardCover property={property} />
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_top,rgba(6,11,19,0.95),transparent_55%,rgba(0,0,0,0.45))]"
          />
          {/* Provenance first (reads as "where from"), property type second.
              The badge carries the full title, so a truncated overlay chip
              still answers "which portal is this?" on hover. */}
          <div className="absolute inset-x-0 top-0 flex items-start justify-between gap-2 p-2.5">
            <span
              className="lux-badge lux-badge-source min-w-0 max-w-[58%] truncate"
              title={SOURCE_LABELS[property.source]}
            >
              {SOURCE_SHORT_LABELS[property.source]}
            </span>
            <span className="lux-badge lux-badge-type shrink-0">
              {PROPERTY_TYPE_LABELS[property.property_type]}
            </span>
          </div>
          {isBargain && (
            <span className="lux-ribbon">
              <Icons.sparkles aria-hidden className="size-3.5" />
              {VALUATION_LABELS.BARGAIN}
            </span>
          )}
          {isExclusive && !isBargain && (
            <span className="lux-ribbon lux-ribbon-exclusive">
              <Icons.exclusive aria-hidden className="size-3.5" />
              پیشنهاد ویژه
            </span>
          )}
          {property.images_count > 1 && (
            /* Same pill as the feed card's, so the photo count reads
               identically everywhere it appears on a listing. */
            <span className="absolute bottom-2.5 end-2.5 inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-black/70 px-2 py-0.5 text-[11px] text-gray-200 backdrop-blur-md">
              <Icons.camera aria-hidden className="size-3.5 text-gold-primary" />
              {`${toPersianDigits(property.images_count.toLocaleString("en-US"))} تصویر`}
            </span>
          )}
        </div>

        <div className="flex min-h-0 flex-1 flex-col gap-2.5 p-3.5">
          <div className="flex min-w-0 flex-col gap-1">
            <h3 className="truncate text-sm font-bold leading-6 text-[#f5f5f7] transition-colors group-hover:text-gold-primary">
              {property.title || PROPERTY_TYPE_LABELS[property.property_type]}
            </h3>
            {/* Always rendered: a missing neighbourhood is information, and a
                line that appears on some cards only is what pushes the spec
                grid — and the whole card — down unevenly across a row. */}
            <p className="flex min-w-0 items-center gap-1 text-[11px] text-[#94a3b8]">
              <Icons.mapPin aria-hidden className="size-3.5 shrink-0 text-gold-accent/80" />
              <span className="truncate">{location || "موقعیت نامشخص"}</span>
            </p>
          </div>

          <SpecGrid property={property} age={age} />

          <div className="h-px w-full bg-gradient-to-r from-transparent via-[var(--lux-divider)] to-transparent" />

          {/* Pinned to the bottom by the spacer-free `mt-auto` on the footer,
              so the price always ends flush with the card's lower edge. */}
          <PriceHud property={property} variant={variant} marketMedian={marketMedian} />
        </div>
      </Link>

      {/* Outside the link, in normal flow: the card is one big anchor, so an
          action placed inside it would navigate instead of acting.

          Deliberately a strip *beneath* the link's own bottom padding rather
          than an overlay on the thumbnail. The thumbnail's bottom-inline-start
          corner is already taken by the valuation/exclusivity ribbon
          (``.lux-ribbon``) and its bottom-inline-end corner by the photo
          counter, so an overlay there lands on top of one of them — and on a
          narrow two-up mobile card the two together would exceed the
          thumbnail's width. In flow the action can cover neither, and it stays
          tappable on a touch screen, where a hover-only affordance would not
          be. The card body's own ``p-3.5`` supplies the gap above it, so this
          only pads the sides and the bottom. */}
      {leadAction && <div className='shrink-0 px-3.5 pb-3.5'>{leadAction}</div>}
    </motion.article>
  );
}

/** Cover photo, or an editorial plate when the node has nothing servable. */
function CardCover({ property }: { property: PropertySummary }) {
  if (!property.cover_url) {
    return (
      <div
        aria-hidden
        className="flex size-full flex-col items-center justify-center gap-2 bg-[radial-gradient(80%_80%_at_50%_20%,rgb(35,52,80,0.9),rgb(6,11,19,1))]"
      >
        <span className="flex size-11 items-center justify-center rounded-full border border-[rgba(229,168,123,0.35)] bg-[rgba(229,168,123,0.08)]">
          <Icons.home aria-hidden className="size-5 text-gold-primary" />
        </span>
        <span className="text-xs font-medium text-[#94a3b8]">
          {DEAL_TYPE_LABELS[property.deal_type]}
        </span>
      </div>
    );
  }
  return (
    /* eslint-disable-next-line @next/next/no-img-element */
    <img src={mediaUrl(property.cover_url)} alt="" loading="lazy" className="lux-card-image size-full object-cover" />
  );
}

/**
 * 2x2 spec grid: area / bedrooms / building age / parking.
 *
 * Each cell puts the icon+label on the inline start and the value on the
 * inline end, so the eye reads the label once and scans values down the
 * column — the layout advisors already know from the portals.
 */
function SpecGrid({ property, age }: { property: PropertySummary; age: string | null }) {
  const cells = [
    {
      icon: <Icons.statArea aria-hidden className="size-3.5 text-gold-accent" />,
      label: "متراژ",
      value:
        property.area !== null
          ? `${toPersianDigits(property.area.toLocaleString("en-US"))} م²`
          : "—"
    },
    {
      icon: <Icons.statBed aria-hidden className="size-3.5 text-gold-accent" />,
      label: "خواب",
      value: property.rooms !== null ? toPersianDigits(property.rooms.toLocaleString("en-US")) : "—"
    },
    {
      icon: <Icons.calendar aria-hidden className="size-3.5 text-gold-accent" />,
      label: "سن بنا",
      value: age ?? "—"
    },
    {
      icon: <Icons.amenityParking aria-hidden className="size-3.5 text-gold-accent" />,
      label: "پارکینگ",
      value: property.has_parking ? "دارد" : "ندارد"
    }
  ];

  return (
    <div className="grid grid-cols-2 gap-1.5 rounded-xl border border-white/[0.06] bg-white/[0.03] p-2">
      {cells.map((cell) => (
        <div
          key={cell.label}
          className="flex items-center justify-between gap-1.5 rounded-lg bg-white/[0.02] px-2 py-1.5"
        >
          <span className="flex min-w-0 items-center gap-1.5 text-[11px] text-[#94a3b8]">
            {cell.icon}
            <span className="truncate">{cell.label}</span>
          </span>
          <span className="shrink-0 text-xs font-semibold tabular-nums text-[#f5f5f7]">
            {cell.value}
          </span>
        </div>
      ))}
    </div>
  );
}

/**
 * The market verdict, as a pill in a reserved slot above the price row.
 *
 * It gets its own row and always claims the same height. A card with no
 * neighbourhood median to be judged against renders the same reserve,
 * empty, instead of nothing at all — so the price row below starts at the
 * same offset on every card in the grid. That offset is what makes a row of
 * cards read as one grid rather than a staircase: the pill can never push a
 * price up on one card and leave it down on the next.
 *
 * The palette is deliberately muted. Jade for an under-market ask, warm bronze
 * for an over-market one, both in the brand's own hue family. The saturated
 * green/red a brokerage terminal would use reads as an alarm on a card whose
 * whole argument is "this property is worth your attention" — at a hundred
 * cards per page that noise is what makes the grid look cheap.
 *
 * One glyph states the direction and the percentage is the figure a broker can
 * actually quote; «زیر قیمت» is a hint, «۱۲٪ زیر عرف» is a number.
 *
 * An equal price, or one with no median, gets the empty reserve: sitting
 * exactly on the market is not a finding worth a label.
 */
function MarketVerdictPill({
  property,
  marketMedian
}: {
  property: PropertySummary;
  marketMedian?: number | null;
}) {
  const figure = comparablePriceOf(property);
  const verdict = marketVerdict(figure, marketMedian);
  const below = verdict.direction === "BELOW";
  const hasVerdict = verdict.direction === "BELOW" || verdict.direction === "ABOVE";

  const magnitude =
    verdict.deviation === null || !Number.isFinite(verdict.deviation)
      ? null
      : toPersianDigits(
          Math.abs(verdict.deviation).toLocaleString("en-US", { maximumFractionDigits: 1 })
        );

  const short = below ? "زیر عرف" : "بالای عرف";
  const long = below ? "زیر عرف منطقه" : "بالای عرف بازار";
  const Icon = below ? Icons.chevronDown : Icons.chevronUp;
  const text = magnitude ? `${magnitude}٪ ${short}` : short;

  /*
   * The pill is always rendered; the box is what does the aligning, so an
   * empty verdict keeps the same element and only stops being visible.
   * `visibility` rather than `display: none` — the latter would remove the
   * box from layout and put the price back out of step with its neighbours.
   */
  return (
    <span
      className={cn(
        "lux-market-pill",
        below ? "lux-market-below" : "lux-market-above",
        !hasVerdict && "invisible"
      )}
      aria-hidden={!hasVerdict}
      title={hasVerdict && magnitude ? `${magnitude}٪ ${long}` : undefined}
    >
      <Icon aria-hidden className="size-3 shrink-0" />
      <span>{hasVerdict ? text : ""}</span>
    </span>
  );
}

/**
 * Price footer: headline figure on the inline start, secondary on the inline
 * end, verdict pill in a reserved slot above both.
 *
 * The row is a two-column grid in *both* deal families — sale shows total price
 * + per-metre, lease shows deposit + monthly rent — so the headline always
 * lands in the same cell and the same size no matter what the row holds. A
 * missing number prints an em dash in its own cell rather than collapsing it,
 * and the short-circuit that used to collapse the whole footer to one line
 * when a lease carried neither figure is gone for the same reason: the columns
 * have to stay where they are.
 *
 * Sale cards compare price per square metre and lease cards compare the
 * deposit, which is why the benchmark is looked up in the unit the listing is
 * itself quoted in — the same aggregation «تحلیل بازار» maps, so the card can
 * be read against the market without opening it.
 */
function PriceHud({
  property,
  variant,
  marketMedian
}: {
  property: PropertySummary;
  variant: ShowcaseVariant;
  marketMedian?: number | null;
}) {
  const isRent = variant === "rent";

  return (
    <div className="mt-auto flex min-w-0 flex-col gap-1.5">
      <MarketVerdictPill property={property} marketMedian={marketMedian} />

      <div className="grid min-w-0 grid-cols-2 items-end gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-medium text-[#94a3b8]">{isRent ? "ودیعه" : "قیمت کل"}</p>
          <p className="truncate text-sm font-extrabold tabular-nums text-gold-primary">
            {formatToman(isRent ? property.deposit_amount : property.total_price)}
          </p>
        </div>
        <div className="min-w-0 text-end">
          <p className="text-[10px] font-medium text-[#94a3b8]">{isRent ? "اجاره ماهانه" : "متری"}</p>
          <p className="truncate text-xs font-semibold tabular-nums text-[#f5f5f7]">
            {isRent
              ? formatToman(property.monthly_rent)
              : formatPricePerMeter(comparablePriceOf(property))}
          </p>
        </div>
      </div>
    </div>
  );
}
