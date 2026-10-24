"use client";

import { Icons } from "@/components/icons";

import { colorAt, type MarketScale } from "../utils/market";

/** The ramp sampled densely enough that the CSS gradient looks continuous. */
const STOPS = Array.from({ length: 11 }, (_, index) => colorAt(index / 10)).join(", ");

/**
 * Colour key for the market map.
 *
 * Right-to-left, like the rest of the page: the cheapest value sits at the
 * start of the bar (the right edge) and the dearest at the end. The gradient is
 * painted `to left` for the same reason — a bar that ran against the text
 * direction would have brokers reading the two ends backwards.
 */
export function MarketLegend({
  scale,
  format,
  unit,
  note
}: {
  scale: MarketScale;
  format: (value: number) => string;
  /** Metric unit, e.g. «تومان/متر». */
  unit: string;
  /** Optional caveat, e.g. coverage of the priced files. */
  note?: string;
}) {
  return (
    <section
      aria-label="راهنمای رنگ نقشه بازار"
      className="border-border/60 bg-card/70 rounded-2xl border p-3 shadow-xs backdrop-blur-sm sm:p-4"
    >
      <header className="border-border/50 flex flex-wrap items-center justify-between gap-2 border-b pb-2.5">
        <div className="min-w-0">
          <h3 className="text-sm leading-6 font-semibold text-foreground">راهنمای رنگ</h3>
          <p className="text-muted-foreground text-xs leading-5">شدت قیمت بر اساس واحد {unit}</p>
        </div>

        {scale.median !== null && (
          <span className="border-border/50 bg-muted/60 inline-flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs whitespace-nowrap">
            <Icons.chart className="text-muted-foreground size-3.5 shrink-0" />
            <span className="text-muted-foreground">میانهٔ محله‌ها:</span>
            <span className="font-semibold tabular-nums text-foreground">
              {format(scale.median)}
            </span>
          </span>
        )}
      </header>

      <div className="flex flex-col gap-2 pt-3 sm:flex-row sm:items-center sm:gap-3">
        <span className="shrink-0 text-xs whitespace-nowrap tabular-nums text-foreground">
          {format(scale.min)}
        </span>
        <div
          className="border-border/40 h-2.5 min-w-32 flex-1 rounded-full border shadow-inner"
          style={{ background: `linear-gradient(to left, ${STOPS})` }}
          role="img"
          aria-label={`مقیاس رنگ از ${format(scale.min)} تا ${format(scale.max)}`}
        />
        <span className="shrink-0 text-xs whitespace-nowrap tabular-nums text-foreground">
          {format(scale.max)}
        </span>
      </div>

      <div className="text-muted-foreground/80 mt-1.5 flex justify-between text-[10px] leading-4 sm:hidden">
        <span>کمترین</span>
        <span>بیشترین</span>
      </div>

      {note && (
        <footer className="border-border/50 bg-muted/30 mt-3 flex items-start gap-2 rounded-xl border px-3 py-2.5">
          <Icons.info className="text-muted-foreground mt-0.5 size-3.5 shrink-0" />
          <p className="text-muted-foreground min-w-0 text-xs leading-5">{note}</p>
        </footer>
      )}
    </section>
  );
}
