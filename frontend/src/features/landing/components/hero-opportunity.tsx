"use client";

import { useQuery } from "@tanstack/react-query";
import { ApiError, fetchBargains } from "@/features/properties/api/client";
import { PROPERTY_TYPE_LABELS } from "@/features/properties/utils/labels";
import { useLandingCity } from "../use-landing-city";
import { toPersianDigits } from "@/lib/utils";

/** Summary of a real radar result; shares the tool-preview query cache. */
export function HeroOpportunity() {
  const city = useLandingCity();
  const query = useQuery({
    queryKey: ["landing-tool-bargains", city],
    queryFn: () => fetchBargains({ city: city ?? undefined, limit: 30 }),
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: false
  });
  const property = query.data?.items.find(
    (item) =>
      item.valuation_status === "BARGAIN" &&
      item.valuation_deviation_pct !== null &&
      Number.isFinite(item.valuation_deviation_pct) &&
      item.valuation_deviation_pct < 0 &&
      item.valuation_deviation_pct > -100
  );
  if (query.isPending || query.isError || !property) {
    const denied = query.error instanceof ApiError && [401, 403].includes(query.error.status);
    return (
      <aside className="landing-hero-opportunity" aria-label="فرصت‌های واقعی زیر قیمت بازار">
        <div className="landing-opportunity-heading">
          <p>فرصت زیر قیمت بازار</p>
        </div>
        <p className="landing-hero-card-state" role="status">
          {query.isPending
            ? "در حال دریافت فرصت‌های بازار…"
            : denied
              ? "مشاهدهٔ رادار قیمت نیازمند ورود و دسترسی مجاز است."
              : query.isError
                ? "دریافت فرصت‌های بازار ممکن نشد."
                : "فرصت دارای ارزش‌گذاری معتبر در داده‌های فعلی یافت نشد."}
        </p>
      </aside>
    );
  }
  const deviation = Math.abs(property.valuation_deviation_pct!);
  const ratio = 100 - deviation;
  const number = (n: number) =>
    toPersianDigits(n.toLocaleString("en-US", { maximumFractionDigits: 2 }));
  return (
    <aside className="landing-hero-opportunity" aria-label="فرصت‌های واقعی زیر قیمت بازار">
      <div className="landing-opportunity-heading">
        <span className="landing-opportunity-icon">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
            <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0M4 2C2.8 3.7 2 5.7 2 8M22 8c0-2.3-.8-4.3-2-6" />
          </svg>
        </span>
        <div>
          <p>فرصت زیر قیمت بازار</p>
          <small>رادار قیمت · دادهٔ سامانه</small>
        </div>
      </div>
      <div className="landing-opportunity-property">
        <p>
          {PROPERTY_TYPE_LABELS[property.property_type] ?? property.title}
          {property.area !== null && Number.isFinite(property.area) && property.area > 0
            ? ` ${number(property.area)} متری`
            : ""}
          {[property.neighborhood, property.city].filter(Boolean).length
            ? ` · ${[property.neighborhood, property.city].filter(Boolean).join(" · ")}`
            : ""}
        </p>
        <div className="landing-opportunity-deviation">
          <span>اختلاف با ارزش AVM</span>
          <strong>{number(deviation)}٪ کمتر</strong>
        </div>
        <div className="landing-opportunity-track">
          <span style={{ width: `${ratio}%` }} />
        </div>
        <small className="landing-opportunity-ratio">
          قیمت پیشنهادی: {number(ratio)}٪ ارزش AVM
        </small>
      </div>
    </aside>
  );
}
