"use client";

import Link from "next/link";
import { Icons } from "@/components/icons";
import { cn, formatPricePerMeter, formatToman, toPersianDigits } from "@/lib/utils";
import type { PropertySummary } from "../types";
import { mediaUrl } from "@/lib/media-url";
import {
  DEAL_TYPE_LABELS,
  PROPERTY_TYPE_LABELS,
  SOURCE_LABELS,
  SOURCE_SHORT_LABELS,
  formatBuildingAge,
  formatFloor,
  formatPublishedAgo
} from "../utils/labels";
import { useAuthContext } from "@/hooks/use-auth";

/**
 * Listing card for the property feed, in the same ultra-luxury treatment as the
 * showcase rails (obsidian glass + rose-gold, 4:3 thumbnail, 2x2 spec grid,
 * price HUD) so inventory reads identically wherever it appears.
 *
 * Structure follows the Iranian portal convention advisors already read on Divar
 * and Sheypoor -- a provenance/type header over the photo, a compact spec grid,
 * then the price block -- so scanning a page of inventory needs no learning.
 * What is added on top is what Shekarchi knows and a portal does not: the AVM
 * verdict against the local median.
 *
 * There is deliberately no `visit_date` anywhere on this card. A listing has no
 * schedule; an appointment belongs on the CRM timeline.
 */

interface ListingCardProps {
  property: PropertySummary;
  className?: string;
  /** Highlights the row in the bargain radar. */
  emphasis?: boolean;
  /** Dense cards for the six-column AVM grid; the property feed stays unchanged. */
  compact?: boolean;
}

export function ListingCard({ property, className, emphasis, compact = false }: ListingCardProps) {
  const { user } = useAuthContext();
  const location = [property.neighborhood, property.city].filter(Boolean).join("، ");
  const age = formatBuildingAge(property.year_built);
  const floor = formatFloor(property.floor, property.total_floors);
  const publishedAgo = formatPublishedAgo(property.updated_at);
  const isBargain = property.valuation_status === "BARGAIN";
  const isRent = property.deal_type === "RENT" || property.deal_type === "FULL_MORTGAGE";

  return (
    <article
      className={cn(
        "lux-card group relative flex h-full min-w-0 flex-col overflow-hidden",
        emphasis && isBargain && "ring-gold-accent ring-2",
        className
      )}
    >
      <Link
        href={user ? `/dashboard/properties/${property.id}` : `/auth/sign-in?callbackUrl=${encodeURIComponent(`/dashboard/properties/${property.id}`)}`}
        aria-label={property.title || PROPERTY_TYPE_LABELS[property.property_type]}
        className="flex h-full flex-col rounded-[inherit] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gold-accent"
      >
        <div
          className={cn(
            "relative w-full shrink-0 overflow-hidden",
            compact ? "aspect-video" : "aspect-4/3"
          )}
        >
          <Cover property={property} />
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_top,rgba(6,11,19,0.95),transparent_55%,rgba(0,0,0,0.45))]"
          />
          {/* Provenance first (reads as "where from"), property type second.
              Compact badge text over the photo; the full label is the tooltip. */}
          <div
            className={cn(
              "absolute inset-x-0 top-0 flex items-start justify-between gap-1",
              compact ? "p-1 [&_.lux-badge]:px-1 [&_.lux-badge]:text-[9px]" : "p-2.5"
            )}
          >
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
          {publishedAgo && (
            <span className="absolute bottom-2.5 end-2.5 inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-black/70 px-2 py-0.5 text-[11px] text-gray-200 backdrop-blur-md">
              <Icons.clock aria-hidden className="size-3.5 text-gold-primary" />
              {publishedAgo}
            </span>
          )}
          {property.images_count > 1 && !publishedAgo && (
            <span className="absolute bottom-2.5 end-2.5 inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-black/70 px-2 py-0.5 text-[11px] text-gray-200 backdrop-blur-md">
              <Icons.camera aria-hidden className="size-3.5 text-gold-primary" />
              {`${toPersianDigits(property.images_count.toLocaleString("en-US"))} تصویر`}
            </span>
          )}
        </div>

        <div
          className={cn(
            "flex min-h-0 flex-1 flex-col justify-between",
            compact ? "gap-2 p-2" : "gap-3 p-3.5"
          )}
        >
          <div className="flex min-w-0 flex-col gap-1">
            <h3
              className={cn(
                "truncate font-bold text-[#f5f5f7] transition-colors group-hover:text-gold-primary",
                compact ? "text-xs leading-5" : "text-sm leading-6"
              )}
            >
              {property.title ||
                `${PROPERTY_TYPE_LABELS[property.property_type]}${location ? ` در ${location}` : ""}`}
            </h3>
            <div
              className={cn(
                "flex min-w-0 items-center gap-1 text-[#94a3b8]",
                compact ? "text-[10px]" : "text-[11px]"
              )}
            >
              <Icons.mapPin aria-hidden className="size-3.5 shrink-0 text-gold-accent/80" />
              <span className="truncate">{location || "موقعیت نامشخص"}</span>
              <span aria-hidden>·</span>
              <span className="shrink-0">{DEAL_TYPE_LABELS[property.deal_type]}</span>
            </div>
          </div>

          {compact ? (
            <div className="grid min-w-0 grid-cols-2 gap-1 rounded-lg border border-white/10 bg-white/5 p-1.5 text-[10px] text-[#cbd5e1]">
              <span className="truncate">
                {property.area == null ? "—" : toPersianDigits(String(property.area))} م²
              </span>
              <span className="truncate">
                {property.rooms == null ? "—" : toPersianDigits(String(property.rooms))} خواب
              </span>
              <span className="truncate" title={floor ?? age ?? ""}>
                {floor ?? age ?? "—"}
              </span>
              <span className="truncate">{property.has_parking ? "پارکینگ" : "بدون پارکینگ"}</span>
            </div>
          ) : (
            <SpecGrid property={property} floor={floor} age={age} />
          )}

          <div className="h-px w-full bg-gradient-to-r from-transparent via-[var(--lux-divider)] to-transparent" />

          <div
            className={
              compact
                ? "[&>div]:flex-col [&>div]:items-stretch [&_p]:text-[10px] [&_.text-end]:text-start"
                : undefined
            }
          >
            <PriceBlock property={property} isRent={isRent} />
          </div>
        </div>
      </Link>
    </article>
  );
}

/**
 * Cover image, or a typographic plate when the node has nothing servable.
 *
 * The API only returns `cover_url` for media the browser can actually fetch, so
 * the no-image case is the common one on a fresh install and is designed rather
 * than left as a grey box.
 */
function Cover({ property }: { property: PropertySummary }) {
  const label = PROPERTY_TYPE_LABELS[property.property_type];

  if (!property.cover_url) {
    return (
      <div
        aria-hidden
        className="flex size-full flex-col items-center justify-center gap-2 bg-[radial-gradient(80%_80%_at_50%_20%,rgb(35,52,80,0.9),rgb(6,11,19,1))]"
      >
        <span className="flex size-11 items-center justify-center rounded-full border border-[rgba(229,168,123,0.35)] bg-[rgba(229,168,123,0.08)]">
          <Icons.home aria-hidden className="size-5 text-gold-primary" />
        </span>
        <span className="text-xs font-medium text-[#94a3b8]">{label}</span>
      </div>
    );
  }

  return (
    <div className="relative size-full">
      {/* Plain <img>: the cover is an arbitrary office/MLS URL with unknown
          dimensions, which next/image cannot optimise without a loader. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={mediaUrl(property.cover_url)}
        alt={property.title || label}
        loading="lazy"
        className="lux-card-image size-full object-cover"
      />
    </div>
  );
}

/**
 * 2×2 spec chip: area, rooms, floor (or build age), and access.
 *
 * Access is the compound one — parking and elevator as a single dot-joined
 * cell, because two one-bit booleans in their own cells would cost half the
 * grid to say "yes". `floor` and `age` arrive already formatted, and either
 * may be null: a listing with no floor reported shows its build age instead,
 * and one with neither shows the em dash rather than an invented value.
 */
function SpecGrid({
  property,
  floor,
  age
}: {
  property: PropertySummary;
  floor: string | null;
  age: string | null;
}) {
  const access =
    [property.has_parking && "پارکینگ", property.has_elevator && "آسانسور"]
      .filter(Boolean)
      .join(" · ") || "—";

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
      icon: <Icons.statAge aria-hidden className="size-3.5 text-gold-accent" />,
      label: floor ? "طبقه" : "سن بنا",
      value: floor ?? age ?? "—"
    },
    {
      icon: <Icons.amenityParking aria-hidden className="size-3.5 text-gold-accent" />,
      label: "دسترسی",
      value: access
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
 * Price block beneath the spec chip: sale shows total + per-meter; rent shows
 * deposit + monthly rent.
 *
 * Total price is the gold figure and every secondary number is one step
 * quieter, so the eye lands on the headline before it reads the breakdown.
 */
function PriceBlock({ property, isRent }: { property: PropertySummary; isRent: boolean }) {
  if (isRent) {
    return (
      <div className="flex items-end justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-medium text-[#94a3b8]">رهن</p>
          <p className="truncate text-sm font-extrabold tabular-nums text-gold-primary">
            {property.deposit_amount !== null ? formatToman(property.deposit_amount) : "—"}
          </p>
        </div>
        <div className="min-w-0 text-end">
          <p className="text-[10px] font-medium text-[#94a3b8]">اجاره ماهانه</p>
          <p className="truncate text-xs font-semibold tabular-nums text-[#f5f5f7]">
            {property.monthly_rent !== null ? formatToman(property.monthly_rent) : "—"}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-end justify-between gap-2">
      <div className="min-w-0">
        <p className="text-[10px] font-medium text-[#94a3b8]">قیمت کل</p>
        <p className="truncate text-sm font-extrabold tabular-nums text-gold-primary">
          {formatToman(property.total_price)}
        </p>
      </div>
      <div className="min-w-0 text-end">
        <p className="text-[10px] font-medium text-[#94a3b8]">متری</p>
        <p className="truncate text-xs font-semibold tabular-nums text-[#94a3b8]">
          {formatPricePerMeter(property.price_per_meter)}
        </p>
      </div>
    </div>
  );
}
