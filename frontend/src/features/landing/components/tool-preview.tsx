"use client";

import { useId } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ApiError,
  fetchBargains,
  fetchNeighbourhoodMarket
} from "@/features/properties/api/client";
import { useLandingCity } from "../use-landing-city";
import { formatPricePerMeter, toPersianDigits } from "@/lib/utils";

const count = (n: number) => toPersianDigits(n.toLocaleString("en-US"));

/** Project only API-provided coordinates; never substitute illustrative locations. */
export function projectLocations<T extends { latitude: number | null; longitude: number | null }>(
  rows: T[]
) {
  const valid = rows.filter(
    (row): row is T & { latitude: number; longitude: number } =>
      row.latitude !== null &&
      row.longitude !== null &&
      Number.isFinite(row.latitude) &&
      Number.isFinite(row.longitude) &&
      Math.abs(row.latitude) <= 90 &&
      Math.abs(row.longitude) <= 180
  );
  const lat = valid.map((row) => row.latitude);
  const lon = valid.map((row) => row.longitude);
  const minLat = Math.min(...lat),
    maxLat = Math.max(...lat);
  const minLon = Math.min(...lon),
    maxLon = Math.max(...lon);
  // A shared scale preserves the geographic shape of the returned sample.
  const longitudeScale = Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180);
  const span = Math.max(maxLat - minLat, (maxLon - minLon) * longitudeScale);
  return valid.map((row) => ({
    row,
    x:
      span > 0 ? 50 + (((row.longitude - (minLon + maxLon) / 2) * longitudeScale) / span) * 64 : 50,
    y: span > 0 ? 50 - ((row.latitude - (minLat + maxLat) / 2) / span) * 64 : 50
  }));
}

export function ToolPreview({ kind }: { kind: "chart" | "map" | "radar" }) {
  const id = useId();
  const city = useLandingCity();
  const market = useQuery({
    queryKey: ["landing-tool-market", city],
    queryFn: () =>
      fetchNeighbourhoodMarket({
        city: city ?? undefined,
        dealTypes: ["SALE"],
        minFiles: 1,
        limit: 100
      }, false),
    enabled: kind !== "radar",
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: false
  });
  const bargains = useQuery({
    queryKey: ["landing-tool-bargains", city],
    queryFn: () => fetchBargains({ city: city ?? undefined, limit: 30 }),
    enabled: kind === "radar",
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: false
  });
  const query = kind === "radar" ? bargains : market;
  const scope = city ?? "همهٔ شهرها";
  const medians = (market.data?.items ?? []).filter(
    (item) =>
      item.median_price_per_meter !== null &&
      Number.isFinite(item.median_price_per_meter) &&
      item.median_price_per_meter > 0
  );
  const locations = projectLocations(market.data?.items ?? []);
  const targets = projectLocations(bargains.data?.items ?? []);
  const empty =
    kind === "chart"
      ? !medians.length
      : kind === "map"
        ? !locations.length
        : !bargains.data?.items.length;
  const denied = query.error instanceof ApiError && [401, 403].includes(query.error.status);
  const maxPrice = Math.max(...medians.map((item) => item.median_price_per_meter!));
  const chartPoints = medians.map(
    (item, i) =>
      `${medians.length === 1 ? 50 : 2 + (i / (medians.length - 1)) * 96},${95 - (item.median_price_per_meter! / maxPrice) * 85}`
  );
  const path = chartPoints.length ? `M${chartPoints.join(" L")}` : "";

  return (
    <div
      className={`landing-preview landing-preview-${kind}`}
      aria-label={`${kind === "chart" ? "قیمت محله‌ها" : kind === "map" ? "پراکندگی محله‌ها" : "رادار املاک"} · ${scope}`}
      aria-busy={query.isFetching}
    >
      {query.isPending ? (
        <p className="landing-preview-state" role="status">
          در حال دریافت داده‌های سامانه…
        </p>
      ) : query.isError ? (
        <div className="landing-preview-state" role="alert">
          <p>{denied ? "مشاهدهٔ آمار نیازمند ورود و دسترسی مجاز است" : "دریافت داده‌ها ممکن نشد"}</p>
          {!denied && (
            <button type="button" onClick={() => void query.refetch()}>
              تلاش دوباره
            </button>
          )}
        </div>
      ) : empty ? (
        <p className="landing-preview-state">
          {kind === "map"
            ? "محلهٔ دارای مختصات موجود نیست"
            : kind === "radar"
              ? "فایل زیر قیمت بازار یافت نشد"
              : "دادهٔ قیمت محله‌ها موجود نیست"}{" "}
          · {scope}
        </p>
      ) : kind === "chart" ? (
        <>
          <div className="landing-chart-summary">
            <div>
              <p>میانهٔ قیمت فروش هر متر · {scope}</p>
              <p>
                <strong className="landing-live-price">
                  {formatPricePerMeter(market.data?.median_price_per_meter)}
                </strong>
              </p>
            </div>
          </div>
          <div className="landing-chart-plot">
            <svg
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              fill="none"
              role="img"
              aria-label="مقایسهٔ میانهٔ قیمت محله‌ها؛ نمودار زمانی نیست"
            >
              <defs>
                <linearGradient id={`${id}-area`} x1="0" y1="0" x2="0" y2="1">
                  <stop stopColor="#e5a87b" stopOpacity=".34" />
                  <stop offset="1" stopColor="#e5a87b" stopOpacity="0" />
                </linearGradient>
              </defs>
              {[30, 55, 80].map((y) => (
                <line
                  key={y}
                  x1="0"
                  x2="100"
                  y1={y}
                  y2={y}
                  stroke="#fff"
                  strokeOpacity=".07"
                  strokeDasharray="3 4"
                  vectorEffect="non-scaling-stroke"
                />
              ))}
              {medians.length > 1 && (
                <>
                  <path d={`${path} L98 100 L2 100 Z`} fill={`url(#${id}-area)`} />
                  <path
                    d={path}
                    stroke="#e5a87b"
                    strokeWidth="2"
                    vectorEffect="non-scaling-stroke"
                  />
                </>
              )}
              {medians.map((item, i) => {
                const [cx, cy] = chartPoints[i].split(",");
                return (
                  <circle
                    key={`${item.city}:${item.neighborhood}`}
                    cx={cx}
                    cy={cy}
                    r="1"
                    fill="#ffd8be"
                  >
                    <title>
                      {item.city} · {item.neighborhood}:{" "}
                      {formatPricePerMeter(item.median_price_per_meter)}
                    </title>
                  </circle>
                );
              })}
            </svg>
          </div>
          <div className="landing-chart-axis">
            <span>{count(medians.length)} محله در پاسخ سامانه</span>
            <span>مقایسهٔ محله‌ها · نه روند زمانی</span>
          </div>
        </>
      ) : kind === "map" ? (
        <>
          <svg
            className="landing-map-art"
            viewBox="0 0 100 100"
            fill="none"
            role="img"
            aria-label="پراکندگی نسبی مختصات محله‌های موجود"
          >
            <defs>
              <pattern id={`${id}-grid`} width="10" height="10" patternUnits="userSpaceOnUse">
                <path d="M0 0H10M0 0V10" stroke="#fff" strokeOpacity=".06" strokeWidth=".3" />
              </pattern>
            </defs>
            <rect width="100" height="100" fill={`url(#${id}-grid)`} />
            {locations.map(({ row, x, y }) => (
              <circle
                key={`${row.city}:${row.neighborhood}`}
                cx={x}
                cy={y}
                r="2"
                fill="#ffd8be"
                fillOpacity=".8"
              >
                <title>
                  {row.city} · {row.neighborhood} · {count(row.all_files)} فایل
                </title>
              </circle>
            ))}
          </svg>
          <span className="landing-preview-badge landing-map-badge">
            {scope} · {count(locations.length)} محله با مختصات
          </span>
          <span className="landing-map-label">پراکندگی نسبی · نه نقشهٔ خیابان‌ها</span>
        </>
      ) : (
        <>
          <div className="landing-radar-disc" aria-hidden="true">
            {[100, 72, 44].map((size) => (
              <span
                key={size}
                className="landing-radar-ring"
                style={{ width: `${size}%`, height: `${size}%` }}
              />
            ))}
            <span className="landing-radar-cross landing-radar-horizontal" />
            <span className="landing-radar-cross landing-radar-vertical" />
            <span className="landing-radar-beam" />
            {targets.map(({ row, x, y }) => (
              <span
                key={row.id}
                className="landing-radar-target landing-preview-dot"
                style={{ left: `${x}%`, top: `${y}%` }}
                title={`${row.title} · ${row.neighborhood}`}
              />
            ))}
          </div>
          <span className="landing-preview-badge landing-radar-badge">
            {count(bargains.data!.items.length)} فایل زیر قیمت در پاسخ سامانه
          </span>
          <span className="landing-preview-badge landing-radar-example">{scope}</span>
          <p className="landing-radar-live-caption">
            {count(targets.length)} فایل دارای مختصات · موقعیت نسبی
          </p>
        </>
      )}
    </div>
  );
}
