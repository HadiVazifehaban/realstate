"use client";

import * as React from "react";

import { Icons } from "@/components/icons";
import PageContainer from "@/components/layout/page-container";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import {
  Combobox,
  ComboboxContent,
  ComboboxInput,
  ComboboxItem,
  ComboboxList
} from "@/components/ui/combobox";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatPricePerMeter, formatToman, toPersianDigits } from "@/lib/utils";

import { useNeighbourhoodMarket, useNeighbourhoodProperties } from "../hooks";
import { useActiveCityName } from "@/store/useCityStore";
import type { PropertySummary } from "../types";
import { useGisAreas } from "../hooks";
import { MarketLegend } from "./market-legend";
import { MarketList, type MarketRow } from "./market-list";
import { MarketMap } from "./market-map";
import type { MarketBubble } from "./market-map-canvas";
import { PropertyAvmSheet } from "./property-avm-sheet";
import { ListingCard } from "./listing-card";
import {
  DEAL_GROUPS,
  DEAL_GROUP_LABELS,
  bubbleRadius,
  colorForValue,
  dealTypesFor,
  metricById,
  metricsFor,
  scaleOf,
  type DealGroup,
  type MarketMetricId
} from "../utils/market";

/**
 * The node's home market.
 *
 * A city is required for the medians to mean anything — averaging Karaj and
 * Tehran into one number describes neither — and this is the city the office
 * trades in. Clearing the filter falls back to the whole book, which the header
 * says out loud.
 */
const DEFAULT_CITY = "تهران";

const PROVINCE_CENTERS = [
  "تهران",
  "اصفهان",
  "شیراز",
  "تبریز",
  "مشهد",
  "کرج",
  "اهواز",
  "قزوین",
  "همدان",
  "ارومیه",
  "رشت",
  "ساری",
  "قوم",
  "یزد",
  "کرمانشاه",
  "زنجان",
  "سنندج",
  "بندرعباس",
  "سمنان",
  "آمل"
] as const;

const MIN_FILES_OPTIONS = [1, 3, 5, 10] as const;

const count = (value: number | null | undefined) =>
  value === null || value === undefined ? "—" : toPersianDigits(value.toLocaleString("en-US"));

/**
 * Market map, modelled on the portal heat maps brokers already read: each
 * neighbourhood is a bubble whose colour is its median and whose size is how
 * much inventory stands behind that median.
 *
 * The data is the office's *own* book (`/properties/market/neighbourhoods`), not
 * a scraped third-party index — which is also why every figure here can be
 * drilled into: the files behind a bubble are the listings on the radar.
 */
export default function AvmPage() {
  // پل City Gate: شهر فعال سراسری، مقدار پیش‌فرض این صفحه است؛
  // کاربر همچنان می‌تواند از فیلتر خود صفحه شهر دیگری ببیند.
  const gateCity = useActiveCityName();
  const { data: gisData } = useGisAreas();
  const [city, setCity] = React.useState<string | undefined>(undefined);
  const [citySearch, setCitySearch] = React.useState<string>("");
  const effectiveCity = city ?? gateCity ?? DEFAULT_CITY;
  const [dealGroup, setDealGroup] = React.useState<DealGroup>("SALE");
  const [metricId, setMetricId] = React.useState<MarketMetricId>("price_per_meter");
  const [minFiles, setMinFiles] = React.useState<number>(3);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [page, setPage] = React.useState(1);

  // Reset page when a new neighbourhood is selected
  React.useEffect(() => {
    setPage(1);
  }, [selectedId]);

  // Sync citySearch with effectiveCity when city changes externally
  React.useEffect(() => {
    setCitySearch(effectiveCity);
  }, [effectiveCity]);

  // Get available cities from GIS data, fall back to PROVINCE_CENTERS
  const availableCities = React.useMemo(() => {
    if (gisData?.cities && gisData.cities.length > 0) {
      return gisData.cities;
    }
    return PROVINCE_CENTERS as readonly string[];
  }, [gisData]);

  const metrics = React.useMemo(() => metricsFor(dealGroup), [dealGroup]);
  const metric = React.useMemo(() => metricById(metricId), [metricId]);

  const { data, isPending, isError, error } = useNeighbourhoodMarket({
    ...(effectiveCity ? { city: effectiveCity } : {}),
    dealTypes: dealTypesFor(dealGroup),
    minFiles,
    limit: 300
  });

  // The files behind the selected bubble: the same feed the inventory page
  // reads, scoped to the neighbourhood so the grid is not the whole book.
  const {
    data: filesData,
    isPending: filesPending,
    isError: filesError
  } = useNeighbourhoodProperties(selectedId, {
    deal_types: dealTypesFor(dealGroup),
    limit: 60,
    offset: (page - 1) * 60
  });

  /** Switching deal family can strand the metric on one the new book cannot answer. */
  const changeDealGroup = (next: DealGroup) => {
    setDealGroup(next);
    setSelectedId(null);
    if (!metricsFor(next).some((item) => item.id === metricId)) {
      setMetricId(metricsFor(next)[0]!.id);
    }
  };

  const model = React.useMemo(() => {
    const items = data?.items ?? [];

    const ranked = items
      .map((stat) => ({ stat, value: metric.pick(stat) }))
      .filter(
        (row): row is { stat: (typeof items)[number]; value: number } =>
          row.value !== null && Number.isFinite(row.value)
      )
      .sort((a, b) => b.value - a.value);

    const scale = scaleOf(ranked.map((row) => row.value));
    const maxFiles = items.reduce((max, stat) => Math.max(max, stat.files), 0);

    const rows: MarketRow[] = ranked.map(({ stat, value }) => ({
      id: stat.neighborhood,
      neighborhood: stat.neighborhood,
      city: stat.city,
      value: metric.format(value),
      files: count(stat.files),
      color: colorForValue(value, scale),
      bargainShare: stat.bargain_share
    }));

    const bubbles: MarketBubble[] = ranked
      .filter(({ stat }) => typeof stat.latitude === "number" && typeof stat.longitude === "number")
      .map(({ stat, value }) => ({
        id: stat.neighborhood,
        lat: stat.latitude as number,
        lng: stat.longitude as number,
        radius: bubbleRadius(stat.files, maxFiles),
        color: colorForValue(value, scale),
        label: stat.neighborhood,
        value: metric.format(value),
        files: count(stat.files),
        selected: stat.neighborhood === selectedId
      }));

    return { rows, bubbles, scale, ranked };
  }, [data, metric, selectedId]);

  const selected = React.useMemo(
    () => model.ranked.find((row) => row.stat.neighborhood === selectedId) ?? null,
    [model.ranked, selectedId]
  );

  const coverage =
    data && data.total_files > 0
      ? `${count(data.priced_files)} از ${count(data.total_files)} فایل این فهرست قیمت دارد؛ میانه‌ها فقط روی همان‌ها حساب شده‌اند.`
      : undefined;

  return (
    <PageContainer
      pageTitle="تحلیل بازار"
      pageDescription="میانهٔ قیمت هر محله از فایل‌های همین نود — رنگ و اندازهٔ حباب‌ها شدت بازار را نشان می‌دهد."
      pageHeaderAction={<PropertyAvmSheet />}
    >
      <div className="space-y-6">
        {/* Statistics Cards */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="محله‌های روی نقشه" value={count(data?.count ?? 0)} icon="mapPin" />
          <StatCard label="فایل‌های فهرست" value={count(data?.total_files ?? 0)} icon="home" />
          <StatCard label="فایل قیمت‌دار" value={count(data?.priced_files ?? 0)} icon="chart" />
          {dealGroup === "SALE" && (
            <StatCard
              label="میانهٔ شهر (تومان/متر)"
              value={
                data?.median_price_per_meter
                  ? formatPricePerMeter(data.median_price_per_meter)
                  : "—"
              }
              icon="chart"
            />
          )}
        </div>

        {/* Filters */}
        <Card>
          <CardContent className="flex flex-wrap items-center gap-4 p-4">
            <div className="flex items-center gap-2">
              <Icons.mapPin className="text-muted-foreground h-4 w-4" />
              <Combobox
                value={effectiveCity}
                onValueChange={(value) => setCity(value === "all" || !value ? undefined : value)}
              >
                <ComboboxInput
                  placeholder="جستجوی شهر..."
                  aria-label="انتخاب شهر"
                  className="min-w-40 text-right"
                  dir="rtl"
                  value={citySearch}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    setCitySearch(e.target.value)
                  }
                  showTrigger
                  showClear
                />
                <ComboboxContent>
                  <ComboboxList dir="rtl">
                    <ComboboxItem value="all">همهٔ شهرها</ComboboxItem>
                    {availableCities
                      .filter((cityName) => cityName.includes(citySearch))
                      .map((cityName) => (
                        <ComboboxItem key={cityName} value={cityName}>
                          {cityName}
                        </ComboboxItem>
                      ))}
                  </ComboboxList>
                </ComboboxContent>
              </Combobox>
            </div>

            <div className="flex items-center gap-2">
              <div className="border-border flex overflow-hidden rounded-lg border">
                {DEAL_GROUPS.map((group) => (
                  <Button
                    key={group}
                    size="sm"
                    variant={group === dealGroup ? "default" : "ghost"}
                    aria-pressed={group === dealGroup}
                    className="rounded-none"
                    onClick={() => changeDealGroup(group)}
                  >
                    {DEAL_GROUP_LABELS[group]}
                  </Button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Icons.chart className="text-muted-foreground h-4 w-4" />
              <div className="flex flex-wrap items-center gap-1.5">
                {metrics.map((item) => (
                  <Button
                    key={item.id}
                    size="sm"
                    variant={item.id === metric.id ? "secondary" : "ghost"}
                    aria-pressed={item.id === metric.id}
                    onClick={() => setMetricId(item.id)}
                  >
                    {item.label}
                  </Button>
                ))}
              </div>
            </div>

            <div className="ml-auto flex items-center gap-2">
              <span className="text-muted-foreground text-xs">حداقل فایل</span>
              <NativeSelect
                size="sm"
                aria-label="حداقل تعداد فایل هر محله"
                value={String(minFiles)}
                onChange={(event: React.ChangeEvent<HTMLSelectElement>) =>
                  setMinFiles(Number(event.target.value))
                }
                className="min-w-24"
              >
                {MIN_FILES_OPTIONS.map((option) => (
                  <NativeSelectOption key={option} value={String(option)}>
                    {toPersianDigits(String(option))}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>
          </CardContent>
        </Card>

        {isPending && (
          <div className="space-y-4">
            <Skeleton className="h-[520px] w-full rounded-xl" />
            <div className="grid gap-4 md:grid-cols-[minmax(20rem,24rem)_minmax(0,1fr)] xl:grid-cols-[minmax(22rem,26rem)_minmax(0,1fr)]">
              <Skeleton className="h-[400px] w-full rounded-xl" />
              <div className="space-y-4">
                <Skeleton className="h-[120px] w-full rounded-xl" />
                <Skeleton className="h-[200px] w-full rounded-xl" />
              </div>
            </div>
          </div>
        )}

        {isError && (
          <Empty className="border">
            <EmptyHeader>
              <Icons.warning className="text-destructive size-6" />
              <EmptyTitle>دریافت آمار بازار ناموفق بود</EmptyTitle>
              <EmptyDescription>
                {(error as Error)?.message ?? "ارتباط با نود آفیس برقرار نشد."}
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}

        {!isPending && !isError && (
          <>
            {model.ranked.length === 0 ? (
              <Empty className="border">
                <EmptyHeader>
                  <Icons.mapPin className="text-muted-foreground size-6" />
                  <EmptyTitle>محله‌ای با این شرط پیدا نشد</EmptyTitle>
                  <EmptyDescription>
                    حداقل تعداد فایل را کم کنید یا شهر را تغییر دهید. محله‌هایی که قیمت هر متر ثبت‌شده
                    ندارند روی نقشه نمی‌آیند.
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-4 items-stretch">
                  {/* ستون چپ: نقشه + راهنمای رنگ — نقشه بقیه ارتفاع ستون را می‌گیرد */}
                  <div className="flex flex-col gap-4 h-full min-w-0 w-full">
                    <MarketMap
                      bubbles={model.bubbles}
                      selectedId={selectedId}
                      onSelect={setSelectedId}
                    />
                    <MarketLegend
                      scale={model.scale}
                      format={metric.format}
                      unit={metric.unit}
                      note={coverage}
                    />
                  </div>

                  {/* ستون راست: فهرست محله‌ها (پنل اسکرول‌خور) — ارتفاع کامل ستون چپ؛ فقط کارت‌ها Scroll می‌شوند */}
                  <div className="flex flex-col h-full w-full min-h-0">
                    <MarketList
                      rows={model.rows}
                      selectedId={selectedId}
                      onSelect={setSelectedId}
                      emptyMessage="محله‌ای با این فیلترها نیست."
                    />
                  </div>
                </div>

              </div>
            )}
          </>
        )}
      </div>
    </PageContainer>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-border bg-card/60 rounded-xl border px-3 py-2">
      <span className="text-muted-foreground block text-[11px]">{label}</span>
      <span className="text-sm font-semibold tabular-nums">{value}</span>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon
}: {
  label: string;
  value: string;
  icon: keyof typeof Icons;
}) {
  const IconComponent = Icons[icon];
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-4">
        <div className="border-border bg-primary/10 flex h-12 w-12 items-center justify-center rounded-lg">
          <IconComponent className="text-primary h-6 w-6" />
        </div>
        <div className="flex-1">
          <p className="text-muted-foreground text-xs">{label}</p>
          <p className="text-lg font-semibold tabular-nums">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * The selected neighbourhood, in numbers.
 *
 * Shows the median *and* the file count behind it: a ۴۹ میلیارد median resting on
 * one file and one resting on thirty look identical on the map, and only one of
 * them is a market.
 */
function SelectedCard({
  row,
  value,
  metricLabel,
  onClear
}: {
  row: {
    neighborhood: string;
    city: string;
    files: number;
    all_files: number;
    median_area: number | null;
    median_price_per_meter: number | null;
    median_total_price: number | null;
    median_deposit: number | null;
    median_monthly_rent: number | null;
    bargain_share: number;
    median_deviation_pct: number | null;
  };
  value: string;
  metricLabel: string;
  onClear: () => void;
}) {
  return (
    <div className="border-border bg-card/60 rounded-xl border p-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">{row.neighborhood}</h2>
          <p className="text-muted-foreground text-xs">{row.city || "شهر نامشخص"}</p>
        </div>
        <Button variant="ghost" size="icon-sm" aria-label="بستن جزئیات" onClick={onClear}>
          <Icons.close className="size-4" />
        </Button>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Badge variant="secondary" className="rounded-sm">
          {metricLabel}: {value}
        </Badge>
        {row.bargain_share > 0 && (
          <Badge variant="outline" className="rounded-sm text-[10px]">
            {toPersianDigits((row.bargain_share * 100).toFixed(0))}٪ زیر بازار
          </Badge>
        )}
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <Field label="فایل قیمت‌دار" value={count(row.files)} />
        <Field label="کل فایل محله" value={count(row.all_files)} />
        <Field
          label="میانهٔ متراژ"
          value={
            row.median_area
              ? `${toPersianDigits(row.median_area.toLocaleString("en-US"))} متر`
              : "—"
          }
        />
        <Field
          label="قیمت هر متر"
          value={row.median_price_per_meter ? formatPricePerMeter(row.median_price_per_meter) : "—"}
        />
        <Field label="میانهٔ قیمت کل" value={formatToman(row.median_total_price)} />
        <Field label="میانهٔ ودیعه" value={formatToman(row.median_deposit)} />
        <Field label="میانهٔ اجارهٔ ماهانه" value={formatToman(row.median_monthly_rent)} />
        <Field
          label="انحراف از میانه"
          value={
            row.median_deviation_pct === null
              ? "—"
              : `${toPersianDigits(row.median_deviation_pct.toFixed(1))}٪`
          }
        />
      </dl>
    </div>
  );
}

function Field({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className={cn("bg-background/40 rounded-lg border px-2 py-1.5", className)}>
      <dt className="text-muted-foreground text-[10px]">{label}</dt>
      <dd className="truncate font-medium tabular-nums">{value}</dd>
    </div>
  );
}

/**
 * The listings behind one neighbourhood's median, as cards.
 *
 * Drilled into from the selected bubble: a broker picks a neighbourhood on the
 * map to see which files the median was computed from, and each card carries
 * its own AVM verdict -- asked price vs the neighbourhood median, green when
 * under, red when over -- plus a one-click recompute that re-runs the engine
 * against the refreshed cohort without leaving the page.
 */
function NeighbourhoodGrid({
  items,
  loading,
  error
}: {
  items: PropertySummary[];
  loading: boolean;
  error: unknown;
}) {
  if (loading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-64 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-destructive/40">
        <CardContent className="flex flex-col items-center gap-2 py-6 text-center">
          <Icons.warning className="text-destructive size-5" />
          <p className="text-sm font-medium">دریافت فایل‌های این محله ناموفق بود.</p>
        </CardContent>
      </Card>
    );
  }

  if (items.length === 0) {
    return (
      <Card>
        <CardContent className="text-muted-foreground py-6 text-center text-xs">
          در این محله فایل فعالی ثبت نشده است.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
      {items.map((property) => (
        <ListingCard
          key={property.id}
          property={property}
          emphasis={property.valuation_status === "BARGAIN"}
        />
      ))}
    </div>
  );
}
