"use client";

import { useId } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError, fetchNeighbourhoodMarket } from "@/features/properties/api/client";
import { useLandingCity } from "../use-landing-city";
import { formatPricePerMeter, toPersianDigits } from "@/lib/utils";

/** A market snapshot, never a fabricated time series or property valuation. */
export function HeroMarket() {
  const id = useId();
  const city = useLandingCity();
  const query = useQuery({
    queryKey: ["landing-tool-market", city],
    queryFn: () =>
      fetchNeighbourhoodMarket({
        city: city ?? undefined,
        dealTypes: ["SALE"],
        minFiles: 1,
        limit: 100
      }),
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: false
  });
  const rows = (query.data?.items ?? []).filter(
    (row) =>
      row.median_price_per_meter !== null &&
      Number.isFinite(row.median_price_per_meter) &&
      row.median_price_per_meter > 0
  );
  const median = query.data?.median_price_per_meter;
  const hasData =
    !query.isPending &&
    !query.isError &&
    rows.length > 0 &&
    median != null &&
    Number.isFinite(median) &&
    median > 0;
  const denied = query.error instanceof ApiError && [401, 403].includes(query.error.status);
  const max = Math.max(...rows.map((row) => row.median_price_per_meter!));
  const points = rows.map(
    (row, index) =>
      `${rows.length === 1 ? 50 : 2 + (index / (rows.length - 1)) * 96},${92 - (row.median_price_per_meter! / max) * 80}`
  );
  const path = points.length ? `M${points.join(" L")}` : "";
  const number = (value: number) => toPersianDigits(value.toLocaleString("en-US"));

  return (
    <aside className="landing-hero-market" aria-label="خلاصهٔ واقعی بازار املاک">
      <div className="landing-market-heading">
        <span className="landing-market-label">
          <i aria-hidden="true" />
          تحلیل بازار · AVM
        </span>
        <span>{city ?? "همهٔ شهرها"}</span>
      </div>
      {!hasData ? (
        <p className="landing-hero-card-state" role="status">
          {query.isPending
            ? "در حال دریافت تحلیل بازار…"
            : denied
              ? "مشاهدهٔ تحلیل بازار نیازمند ورود و دسترسی مجاز است."
              : query.isError
                ? "دریافت تحلیل بازار ممکن نشد."
                : "دادهٔ معتبر قیمت محله‌ها موجود نیست."}
        </p>
      ) : (
        <>
          <p className="landing-market-caption">میانهٔ قیمت پیشنهادی هر متر مربع</p>
          <p className="landing-market-price">{formatPricePerMeter(median)}</p>
          <div className="landing-market-sparkline">
            <svg
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              role="img"
              aria-label="مقایسهٔ میانهٔ قیمت محله‌ها؛ نه روند زمانی"
            >
              <defs>
                <linearGradient id={`${id}-area`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor="#e5a87b" stopOpacity="0.34" />
                  <stop offset="1" stopColor="#e5a87b" stopOpacity="0" />
                </linearGradient>
                <linearGradient id={`${id}-line`}>
                  <stop stopColor="#c88252" />
                  <stop offset="1" stopColor="#ffd8be" />
                </linearGradient>
              </defs>
              {rows.length > 1 && (
                <>
                  <path d={`${path} L98 100 L2 100 Z`} fill={`url(#${id}-area)`} />
                  <path
                    d={path}
                    fill="none"
                    stroke={`url(#${id}-line)`}
                    strokeWidth="2"
                    strokeLinecap="round"
                    vectorEffect="non-scaling-stroke"
                  />
                </>
              )}
              {rows.map((row, index) => {
                const [cx, cy] = points[index].split(",");
                return (
                  <circle
                    key={`${row.city}:${row.neighborhood}`}
                    cx={cx}
                    cy={cy}
                    r="1.4"
                    fill="#ffd8be"
                  >
                    <title>
                      {row.city} · {row.neighborhood}:{" "}
                      {formatPricePerMeter(row.median_price_per_meter)}
                    </title>
                  </circle>
                );
              })}
            </svg>
          </div>
          <div className="landing-market-footnote">
            <span>{number(rows.length)} محله در پاسخ سامانه</span>
            <strong>مقایسهٔ محله‌ها</strong>
          </div>
          <small className="landing-opportunity-ratio">
            نه روند زمانی یا رشد ماهانه · نه ارزش‌گذاری یک ملک
          </small>
        </>
      )}
    </aside>
  );
}
