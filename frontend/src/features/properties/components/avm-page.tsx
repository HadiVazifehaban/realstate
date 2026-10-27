"use client";

import * as React from "react";

import { Icons } from "@/components/icons";
import PageContainer from "@/components/layout/page-container";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Combobox,
  ComboboxContent,
  ComboboxInput,
  ComboboxItem,
  ComboboxList
} from "@/components/ui/combobox";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { formatPricePerMeter, toPersianDigits } from "@/lib/utils";

import { useNeighbourhoodMarket, useNeighbourhoodProperties } from "../hooks";
import { useLocationFilter } from "../hooks/use-location-filter";
import type { PropertySummary } from "../types";
import { useGisAreas } from "../hooks";
import { MarketLegend } from "./market-legend";
import { MarketList, type MarketRow } from "./market-list";
import { MarketMap } from "./market-map";
import type { MarketBubble } from "./market-map-canvas";
import { PropertyAvmSheet } from "./property-avm-sheet";
import { ListingCard } from "./listing-card";
import { SelectedNeighbourhoodCard } from "./selected-neighbourhood-card";
import "./avm-workspace.css";
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
  const { cities, setCities } = useLocationFilter();
  const { data: gisData } = useGisAreas();
  const [citySearch, setCitySearch] = React.useState<string>("");
  const effectiveCity = cities.length === 1 ? cities[0] : "";
  const [dealGroup, setDealGroup] = React.useState<DealGroup>("SALE");
  const [metricId, setMetricId] = React.useState<MarketMetricId>("price_per_meter");
  const [rangeMin, setRangeMin] = React.useState("");
  const [rangeMax, setRangeMax] = React.useState("");
  const [minFiles, setMinFiles] = React.useState<number>(3);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const selectedLocation = selectedId ? JSON.parse(selectedId) as [string, string] : null;
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
    ...(cities.length ? { cities } : {}),
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
  } = useNeighbourhoodProperties(selectedLocation?.[1] ?? null, {
    city: selectedLocation?.[0],
    deal_types: dealTypesFor(dealGroup),
    limit: 60,
    offset: (page - 1) * 60
  });

  /** Switching deal family can strand the metric on one the new book cannot answer. */
  const changeDealGroup = (next: DealGroup) => {
    setDealGroup(next);
    setRangeMin("");
    setRangeMax("");
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

    const visible = ranked.filter(
      ({ value }) =>
        (rangeMin === "" || value >= Number(rangeMin)) &&
        (rangeMax === "" || value <= Number(rangeMax))
    );
    const rows: MarketRow[] = visible.map(({ stat, value }) => ({
      id: JSON.stringify([stat.city, stat.neighborhood]),
      neighborhood: stat.neighborhood,
      city: stat.city,
      value: metric.format(value),
      files: count(stat.files),
      color: colorForValue(value, scale),
      bargainShare: stat.bargain_share
    }));

    const bubbles: MarketBubble[] = visible
      .filter(({ stat }) => typeof stat.latitude === "number" && typeof stat.longitude === "number")
      .map(({ stat, value }) => ({
        id: JSON.stringify([stat.city, stat.neighborhood]),
        lat: stat.latitude as number,
        lng: stat.longitude as number,
        radius: bubbleRadius(stat.files, maxFiles),
        color: colorForValue(value, scale),
        label: stat.neighborhood,
        value: metric.format(value),
        files: count(stat.files),
        selected: JSON.stringify([stat.city, stat.neighborhood]) === selectedId
      }));

    return { rows, bubbles, scale, ranked: visible };
  }, [data, metric, selectedId, rangeMin, rangeMax]);

  const selected = React.useMemo(
    () => model.ranked.find((row) => JSON.stringify([row.stat.city, row.stat.neighborhood]) === selectedId) ?? null,
    [model.ranked, selectedId]
  );

  // Keep the detail bar and its listings useful on first load and city changes.
  React.useEffect(() => {
    if (!model.ranked.some(({ stat }) => JSON.stringify([stat.city, stat.neighborhood]) === selectedId)) {
      const first = model.ranked[0]?.stat;
      setSelectedId(first ? JSON.stringify([first.city, first.neighborhood]) : null);
    }
  }, [model.ranked, selectedId]);

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
      <div
        className="avm-page mx-auto w-full max-w-[1800px] min-w-0 space-y-3 text-right font-[family-name:var(--font-vazir)]"
        dir="rtl"
      >
        {/* Statistics Cards */}
        <div className="avm-statistics grid grid-cols-2 gap-2 lg:grid-cols-4">
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

        <section aria-label="نقشه و رتبه‌بندی محله‌ها" className="avm-workspace" dir="rtl">
          <aside aria-label="محله‌ها و فایل‌های مرتبط" className="avm-right-column">
            {isPending ? (
              <Skeleton className="h-full min-h-80 w-full" />
            ) : isError ? (
              <div role="alert" className="avm-state">
                دریافت آمار بازار ناموفق بود: {(error as Error)?.message ?? "ارتباط برقرار نشد."}
              </div>
            ) : (
              <>
                <aside aria-label="رتبه‌بندی محله‌ها" className="avm-neighborhoods">
                  <div className="flex h-full min-h-0 flex-col">
                    <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-[#e5a87b]/15 bg-[#060b13] px-4 py-3">
                      <h2 className="text-xs font-medium text-[#ffd8be]">
                        محله‌های {effectiveCity}
                      </h2>
                      <span className="text-[10px] text-white/50">جستجوی سریع و رتبه‌بندی</span>
                    </div>
                    <MarketList
                      rows={model.rows}
                      selectedId={selectedId}
                      onSelect={setSelectedId}
                      emptyMessage="محله‌ای با این فیلترها نیست."
                    />
                  </div>
                </aside>
                {selected ? (
                  <>
                    <section aria-label="املاک محلهٔ انتخاب‌شده" className="avm-listings">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h2 className="text-xs font-bold text-gold-primary">
                          املاک {selected.stat.neighborhood}
                        </h2>
                        <span className="text-muted-foreground text-[11px]">
                          اسکرول برای مشاهدهٔ موارد بیشتر · صفحهٔ {count(page)}
                        </span>
                      </div>
                      <div
                        key={`${effectiveCity}:${selectedId}:${page}:${dealGroup}`}
                        role="region"
                        aria-label="فهرست اسکرول‌شوندهٔ املاک"
                        tabIndex={0}
                        className="avm-listings-scroll custom-scrollbar"
                      >
                        <NeighbourhoodGrid
                          items={filesData?.items ?? []}
                          loading={filesPending}
                          error={filesError}
                        />
                      </div>
                      <nav aria-label="صفحه‌بندی املاک" className="flex justify-center gap-3">
                        <Button
                          variant="outline"
                          disabled={page === 1 || filesPending}
                          onClick={() => setPage((p) => p - 1)}
                        >
                          صفحهٔ قبل
                        </Button>
                        <Button
                          variant="outline"
                          disabled={
                            filesPending || !!filesError || (filesData?.items.length ?? 0) < 60
                          }
                          onClick={() => setPage((p) => p + 1)}
                        >
                          صفحهٔ بعد
                        </Button>
                      </nav>
                    </section>
                  </>
                ) : (
                  <p className="avm-state">
                    محله‌ای با این فیلترها پیدا نشد؛ محدودهٔ شاخص یا حداقل فایل را تغییر دهید.
                  </p>
                )}
              </>
            )}
          </aside>
          <aside aria-label="کنترل‌ها و مشخصات محله" className="avm-center-column custom-scrollbar">
            <section aria-label="فیلترهای تحلیل بازار" className="avm-filters">
              <div className="avm-filter-fields">
                <h2 className="text-xs font-bold text-[#ffd8be]">تنظیمات تحلیل</h2>
                <div className="flex items-center gap-2">
                  <Icons.mapPin className="text-muted-foreground h-4 w-4" />
                  <Combobox
                    value={effectiveCity}
                    onValueChange={(value) =>
                      setCities(value === "all" || !value ? [] : [value])
                    }
                  >
                    <ComboboxInput
                      placeholder="جستجوی شهر..."
                      aria-label="انتخاب شهر"
                      className="w-full min-w-0 text-right"
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
                        onClick={() => {
                          setMetricId(item.id);
                          setRangeMin("");
                          setRangeMax("");
                        }}
                      >
                        {item.label}
                      </Button>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-between gap-2">
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
                <fieldset className="avm-range-fields">
                  <legend>
                    محدودهٔ {metric.label} ({metric.unit})
                  </legend>
                  <label>
                    از
                    <input
                      aria-label="حداقل مقدار شاخص محله"
                      type="number"
                      min="0"
                      value={rangeMin}
                      onChange={(e) => setRangeMin(e.target.value)}
                    />
                  </label>
                  <label>
                    تا
                    <input
                      aria-label="حداکثر مقدار شاخص محله"
                      type="number"
                      min="0"
                      value={rangeMax}
                      onChange={(e) => setRangeMax(e.target.value)}
                    />
                  </label>
                  <p>
                    فقط محله‌ها و حباب‌های همین شاخص را محدود می‌کند؛ آمار بر پایهٔ تمام فایل‌های محله
                    است.
                  </p>
                  {rangeMin !== "" && rangeMax !== "" && Number(rangeMin) > Number(rangeMax) && (
                    <p role="alert">حداقل نباید بیشتر از حداکثر باشد.</p>
                  )}
                  {(rangeMin !== "" || rangeMax !== "") && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setRangeMin("");
                        setRangeMax("");
                      }}
                    >
                      پاک‌کردن محدوده
                    </Button>
                  )}
                </fieldset>
              </div>
            </section>

            <div
              className="avm-district-legend"
              role="region"
              aria-label="مشخصات محله و راهنمای نقشه"
            >
              {selected ? (
                <SelectedNeighbourhoodCard
                  key={`${selected.stat.city}:${selected.stat.neighborhood}`}
                  row={selected.stat}
                  compact
                  vertical
                />
              ) : (
                <p className="avm-state">برای نمایش مشخصات، یک محله انتخاب کنید.</p>
              )}
              <MarketLegend
                scale={model.scale}
                format={metric.format}
                unit={metric.unit}
                note={coverage}
                compact
              />
            </div>
          </aside>
          <section id="market-map" aria-label="نقشهٔ بازار" className="avm-map-panel">
            <header>
              <h2>نقشهٔ تحلیل بازار</h2>
              <span>
                {effectiveCity} · {metric.label}
              </span>
            </header>
            <MarketMap bubbles={model.bubbles} selectedId={selectedId} onSelect={setSelectedId} />
          </section>
        </section>
      </div>
    </PageContainer>
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
      <CardContent className="flex items-center gap-3 p-3">
        <div className="border-border bg-primary/10 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg">
          <IconComponent className="text-primary h-4 w-4" />
        </div>
        <div className="flex-1">
          <p className="text-muted-foreground text-xs">{label}</p>
          <p className="text-base font-semibold tabular-nums">{value}</p>
        </div>
      </CardContent>
    </Card>
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
      <div
        dir="rtl"
        className="avm-property-grid grid min-w-0 grid-cols-1 items-stretch gap-2 min-[390px]:grid-cols-2"
      >
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-60 w-full rounded-xl" />
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
    <div
      dir="rtl"
      className="avm-property-grid grid min-w-0 grid-cols-1 items-stretch gap-2 min-[390px]:grid-cols-2"
    >
      {items.map((property) => (
        <ListingCard
          key={property.id}
          property={property}
          compact
          emphasis={property.valuation_status === "BARGAIN"}
        />
      ))}
    </div>
  );
}
