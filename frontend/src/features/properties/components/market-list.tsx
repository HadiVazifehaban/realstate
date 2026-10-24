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
      className="flex-1 overflow-y-auto min-h-0 custom-scrollbar pr-1 space-y-2 pb-2 font-[family-name:var(--font-vazir)]"
      dir="rtl"
    >
      {rows.map((row, index) => (
        <button
          key={row.id}
          type="button"
          onClick={() => onSelect(row.id)}
          aria-current={row.id === selectedId ? "true" : undefined}
          className={cn(
            "group relative w-full overflow-hidden rounded-2xl border border-border/60 bg-card/70 text-right shadow-xs transition-[border-color,background-color,box-shadow,transform] duration-200 hover:-translate-y-px hover:border-primary/50 hover:bg-primary/5 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2",
            row.id === selectedId && "border-primary bg-primary/10 shadow-md ring-1 ring-primary/20"
          )}
        >
          <div
            className="flex items-center gap-3 rounded-xl border border-border/50 bg-card/60 p-3.5 text-right backdrop-blur-md sm:gap-4"
            dir="rtl"
          >
            {/* Right side in RTL: rank, market indicator and neighborhood. */}
            <div className="flex min-w-0 flex-1 items-center gap-3">
              <span
                className={cn(
                  "flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-bold",
                  row.id === selectedId
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
                )}
              >
                {toPersianDigits(String(index + 1))}
              </span>

              <span
                className="size-2.5 shrink-0 rounded-full ring-2 ring-background"
                style={{ backgroundColor: row.color }}
                aria-hidden
              />

              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                {/* No truncation: long neighborhood names wrap instead of being cut. */}
                <span className="break-words text-sm leading-6 font-bold text-foreground sm:text-base">
                  {row.neighborhood}
                </span>

                <span className="flex flex-wrap items-center gap-1.5 text-xs leading-5 text-muted-foreground">
                  <span className="whitespace-nowrap">{row.city || "شهر نامشخص"}</span>
                  <span className="text-muted-foreground/50" aria-hidden>
                    ·
                  </span>
                  <span className="whitespace-nowrap">{row.files} فایل</span>
                  {row.bargainShare > 0 && (
                    <Badge
                      variant="secondary"
                      className="h-4 shrink-0 rounded-md px-1 py-0 text-[9px] leading-none"
                    >
                      <Icons.trendingDown className="size-2.5" />
                      {toPersianDigits((row.bargainShare * 100).toFixed(0))}٪ ارزان
                    </Badge>
                  )}
                </span>
              </div>
            </div>

            {/* Left side in RTL: a dedicated, non-overlapping price column. */}
            <div className="flex shrink-0 flex-col items-start gap-0.5 pl-2 text-left" dir="ltr">
              <span
                className={cn(
                  "text-sm leading-6 font-extrabold tabular-nums whitespace-nowrap sm:text-base",
                  row.id === selectedId ? "text-primary" : "text-foreground"
                )}
              >
                {row.value}
              </span>
              <span className="text-xs leading-4 whitespace-nowrap text-muted-foreground">
                تومان/متر
              </span>
            </div>

            <Icons.chevronRight
              className={cn(
                "-rotate-180 size-4 shrink-0 text-muted-foreground/60 transition-transform duration-200",
                row.id === selectedId && "-rotate-90 text-primary"
              )}
              aria-hidden
            />
          </div>
        </button>
      ))}
    </div>
  );
}
