"use client";

import { Icons } from "@/components/icons";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger } from "@/components/ui/select";

import {
  LEAD_SOURCE_LABELS,
  PROPERTY_SOURCES,
  leadSourceBadge,
  type PropertySource
} from "../types";

const fa = new Intl.NumberFormat("fa-IR");

export const SOURCE_ANY = "ALL_SOURCES";

/**
 * Value → label, for the trigger.
 *
 * The board renders its label from this map instead of `SelectValue`, which
 * resolves the text from the mounted items — the popup is unmounted while
 * closed, so that element reads as the raw value (`ALL_SOURCES`, `DIVAR`) until
 * the list has been opened once.
 */
const SOURCE_LABELS: Record<string, string> = {
  [SOURCE_ANY]: "همهٔ منابع",
  ...Object.fromEntries(PROPERTY_SOURCES.map((source) => [source, LEAD_SOURCE_LABELS[source]]))
};

/**
 * Board filter state.
 *
 * Deliberately client-side and shallow: the node returns the whole pipeline in
 * one feed, so filtering here is instant and does not cost a round trip per
 * keystroke. `query` is debounced by the caller only in the sense that it is
 * cheap — there is no server work behind it.
 */
export interface BoardFilters {
  query: string;
  bargainsOnly: boolean;
  source: PropertySource | typeof SOURCE_ANY;
}

export const EMPTY_FILTERS: BoardFilters = {
  query: "",
  bargainsOnly: false,
  source: SOURCE_ANY
};

export function isFiltering(filters: BoardFilters): boolean {
  return filters.query.trim().length > 0 || filters.bargainsOnly || filters.source !== SOURCE_ANY;
}

/** Apply the filters to a lead list — the single source of truth for the board. */
export function matchesFilters(
  lead: {
    title: string;
    neighborhood: string;
    city: string;
    source: string | null;
    is_bargain: boolean;
  },
  filters: BoardFilters
): boolean {
  if (filters.bargainsOnly && !lead.is_bargain) return false;
  if (filters.source !== SOURCE_ANY && lead.source !== filters.source) return false;

  const query = filters.query.trim().toLowerCase();
  if (!query) return true;
  return [lead.title, lead.neighborhood, lead.city]
    .filter(Boolean)
    .some((field) => field.toLowerCase().includes(query));
}

interface BoardToolbarProps {
  filters: BoardFilters;
  onChange: (next: BoardFilters) => void;
  /** Cards currently on the board, after filtering. */
  visible: number;
  /** Cards on the board before filtering. */
  total: number;
}

/**
 * Filter row above the columns.
 *
 * Every control here narrows what is already loaded, so the count beside them
 * is honest: "۱۲ از ۴۰" means twelve of the forty cards the desk holds, not a
 * page of a larger set the broker cannot reach.
 */
export function BoardToolbar({ filters, onChange, visible, total }: BoardToolbarProps) {
  return (
    <div
      className="crm-board-toolbar border-border bg-card/60 mb-4 flex flex-wrap items-center gap-2 rounded-xl border p-3"
      role="search"
      aria-label="فیلتر پرونده‌ها"
    >
      <div className="relative w-full min-w-0 sm:w-auto sm:min-w-56 sm:flex-1">
        <Icons.search className="text-muted-foreground absolute top-1/2 right-3 size-4 -translate-y-1/2" />
        <Input
          value={filters.query}
          onChange={(event) => onChange({ ...filters, query: event.target.value })}
          placeholder="جست‌وجوی عنوان، محله یا شهر…"
          className="h-10 pr-9"
          aria-label="جست‌وجو در تخته"
        />
      </div>

      <Button
        size="sm"
        variant={filters.bargainsOnly ? "default" : "outline"}
        aria-pressed={filters.bargainsOnly}
        onClick={() => onChange({ ...filters, bargainsOnly: !filters.bargainsOnly })}
      >
        <Icons.trendingDown className="size-4" />
        فقط شکارها
      </Button>

      <Select
        value={filters.source}
        onValueChange={(value) => onChange({ ...filters, source: value as BoardFilters["source"] })}
      >
        <SelectTrigger size="sm" className="w-44 max-w-full" aria-label="منبع آگهی">
          {/*
            The label is rendered from the current filter rather than from
            `SelectValue`: Base UI resolves that element's text from the mounted
            items, and the popup is unmounted while closed -- so the trigger
            would read `ALL_SOURCES` / `DIVAR` until the list was opened once.
          */}
          <span className="flex-1 text-start">
            {SOURCE_LABELS[String(filters.source)] ?? "همهٔ منابع"}
          </span>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={SOURCE_ANY}>همهٔ منابع</SelectItem>
          {PROPERTY_SOURCES.map((source) => (
            <SelectItem key={source} value={source}>
              {LEAD_SOURCE_LABELS[source]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <span
        className="text-muted-foreground ms-auto rounded-lg bg-muted/50 px-3 py-2 text-xs tabular-nums"
        role="status"
      >
        {fa.format(visible)}
        {visible !== total && ` از ${fa.format(total)}`} کارت روی تخته
      </span>

      {isFiltering(filters) && (
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onChange({ ...filters, ...EMPTY_FILTERS })}
        >
          <Icons.close className="size-4" />
          پاک کردن فیلتر
        </Button>
      )}
    </div>
  );
}

/** Small provenance pill reused by the card and the detail sheet. */
export function SourceBadge({ source }: { source: string | null }) {
  const label = leadSourceBadge(source);
  if (!label) return null;
  return (
    <Badge
      variant="outline"
      className="text-muted-foreground pointer-events-none w-fit shrink-0 rounded-sm text-[10px]"
    >
      {label}
    </Badge>
  );
}
