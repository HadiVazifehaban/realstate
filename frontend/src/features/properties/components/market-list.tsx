"use client";

import { Icons } from "@/components/icons";
import { Badge } from "@/components/ui/badge";
import { cn, toPersianDigits } from "@/lib/utils";

/**
 * One row of the ranking, already resolved by the page.
 *
 * The list is deliberately dumb: the page owns the scale, so a row cannot pick
 * a colour that disagrees with its own bubble on the map next to it.
 */
export interface MarketRow {
  id: string;
  neighborhood: string;
  city: string;
  /** The metric value, already formatted. */
  value: string;
  files: string;
  color: string;
  /** 0..1 share of files the AVM judged below market. */
  bargainShare: number;
}

export function MarketList({
  rows,
  selectedId,
  onSelect,
  emptyMessage
}: {
  rows: MarketRow[];
  selectedId?: string | null;
  onSelect: (id: string) => void;
  emptyMessage: string;
}) {
  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed p-8 text-center">
        <Icons.mapPin className="text-muted-foreground mb-2 h-8 w-8" />
        <p className="text-muted-foreground text-sm">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div
      className="custom-scrollbar min-h-0 flex-1 space-y-1.5 overflow-y-auto overscroll-contain p-2 font-[family-name:var(--font-vazir)]"
      dir="rtl"
    >
      {rows.map((row, index) => (
        <button
          key={row.id}
          type="button"
          onClick={() => onSelect(row.id)}
          aria-current={row.id === selectedId ? "true" : undefined}
          className={cn(
            "group relative w-full overflow-hidden rounded-xl border border-transparent bg-white/[0.02] text-right transition-colors hover:border-[#e5a87b]/30 hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#ffd8be]/60",
            row.id === selectedId &&
              "border-[#e5a87b]/50 bg-[#e5a87b]/10 ring-1 ring-inset ring-[#e5a87b]/20"
          )}
        >
          <div className="flex items-center justify-between gap-2 p-2 text-right" dir="rtl">
            {/* Right side in RTL: rank, market indicator and neighborhood. */}
            <div className="flex min-w-0 flex-1 items-center gap-2.5">
              <span
                className={cn(
                  "flex size-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold",
                  row.id === selectedId
                    ? "bg-[#ffd8be] text-[#060b13]"
                    : "bg-[#e5a87b]/10 text-[#ffd8be]"
                )}
              >
                {toPersianDigits(String(index + 1))}
              </span>

              <span
                className="size-1.5 shrink-0 rounded-full"
                style={{ backgroundColor: row.color }}
                aria-hidden
              />

              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span
                  title={row.neighborhood}
                  className="block truncate text-xs font-semibold leading-5 text-white transition-colors group-hover:text-[#ffd8be]"
                >
                  {row.neighborhood}
                </span>

                <span className="flex flex-wrap items-center gap-1 text-[10px] leading-4 text-white/50">
                  <span className="whitespace-nowrap">{row.city || "شهر نامشخص"}</span>
                  <span className="text-muted-foreground/50" aria-hidden>
                    ·
                  </span>
                  <span className="whitespace-nowrap">{row.files} فایل</span>
                  {row.bargainShare > 0 && (
                    <Badge
                      variant="secondary"
                      className="h-4 shrink-0 rounded-md bg-[#e5a87b]/10 px-1 py-0 text-[9px] leading-none text-[#ffd8be]"
                    >
                      <Icons.trendingDown className="size-2.5" />
                      {toPersianDigits((row.bargainShare * 100).toFixed(0))}٪ ارزان
                    </Badge>
                  )}
                </span>
              </div>
            </div>

            {/* Left side in RTL: a dedicated, non-overlapping price column. */}
            <div className="max-w-[48%] shrink-0 text-left" dir="rtl">
              <span className="block text-xs font-bold leading-5 text-[#ffd8be] tabular-nums">
                {row.value}
              </span>
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}
