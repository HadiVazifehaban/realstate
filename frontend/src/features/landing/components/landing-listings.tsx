"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { IconSearch, IconArrowUpLeft } from "@tabler/icons-react";
import {
  ApiError,
  fetchProperties,
  type PropertyListFilters
} from "@/features/properties/api/client";
import { ListingCard } from "@/features/properties/components/listing-card";
import { PROPERTY_TYPES } from "@/features/properties/types";
import { PROPERTY_TYPE_LABELS } from "@/features/properties/utils/labels";
import { useLandingCity } from "../use-landing-city";
import { toPersianDigits } from "@/lib/utils";

type Showcase = "latest" | "bargains" | "agency";
const showcases: { id: Showcase; title: string }[] = [
  { id: "latest", title: "تازه‌ترین آگهی‌ها" },
  { id: "bargains", title: "فرصت‌های زیر قیمت بازار" },
  { id: "agency", title: "فایل‌های دفاتر" }
];
const empty = { q: "", city: "", neighborhood: "", property_type: "", max_price: "", min_area: "" };

export function LandingListings() {
  const city = useLandingCity();
  const [draft, setDraft] = useState(empty);
  const [applied, setApplied] = useState(empty);
  useEffect(() => {
    setDraft((previous) => ({ ...previous, city: "", neighborhood: "" }));
    setApplied((previous) => ({ ...previous, city: "", neighborhood: "" }));
  }, [city]);
  const [deal, setDeal] = useState("all");
  const [showcase, setShowcase] = useState<Showcase>("latest");
  const filters: PropertyListFilters = {
    status: "ACTIVE",
    limit: 6,
    offset: 0,
    q: applied.q.trim() || undefined,
    city: applied.city.trim() || city,
    neighborhood: applied.neighborhood.trim() || undefined,
    property_type: applied.property_type || undefined,
    max_price: applied.max_price ? Number(applied.max_price) : undefined,
    min_area: applied.min_area ? Number(applied.min_area) : undefined,
    deal_type: deal === "sale" ? "SALE" : deal === "rent" ? ["RENT", "FULL_MORTGAGE"] : undefined,
    valuation_status: showcase === "bargains" ? "BARGAIN" : undefined,
    submitter_type: showcase === "agency" ? "AGENCY" : undefined
  };
  const listings = useQuery({
    queryKey: ["properties", "landing-showcase", filters],
    queryFn: () => fetchProperties(filters, false),
    staleTime: 30_000,
    retry: false
  });
  const unauthorized =
    listings.error instanceof ApiError && [401, 403].includes(listings.error.status);
  const update = (field: keyof typeof empty, value: string) =>
    setDraft((previous) => ({ ...previous, [field]: value }));

  return (
    <section
      id="search"
      className="landing-container landing-listings"
      aria-labelledby="listing-showcase-heading"
    >
      <div className="landing-section-heading">
        <p className="landing-kicker">جستجو و ویترین املاک</p>
        <span className="landing-section-english" lang="en">
          PROPERTY SEARCH & SHOWCASE
        </span>
        <h2 id="listing-showcase-heading">ملک مورد نظرتان را هوشمندانه شکار کنید</h2>
        <p>شهر، نوع ملک، بودجه و متراژ را انتخاب کنید؛ آگهی‌های موجود سامانه را همین‌جا ببینید.</p>
      </div>
      <form
        className="landing-search-panel"
        aria-label="فیلتر آگهی‌های ویترین"
        onSubmit={(event) => {
          event.preventDefault();
          setApplied({ ...draft });
        }}
      >
        <div className="landing-search-main">
          <label className="landing-search-query">
            جستجو در آگهی‌ها
            <span>
              <IconSearch size={20} aria-hidden />
              <input
                type="search"
                maxLength={80}
                value={draft.q}
                onChange={(event) => update("q", event.target.value)}
                placeholder="عنوان یا محله، مثلاً آپارتمان یا زعفرانیه"
              />
            </span>
          </label>
          <div className="landing-filter-segments" role="group" aria-label="نوع معامله">
            {[
              ["all", "همه"],
              ["sale", "فروش"],
              ["rent", "رهن و اجاره"]
            ].map(([value, title]) => (
              <button
                type="button"
                key={value}
                aria-pressed={deal === value}
                onClick={() => setDeal(value)}
              >
                {title}
              </button>
            ))}
          </div>
          <button type="submit" className="landing-button landing-button-primary">
            <IconSearch size={18} aria-hidden />
            جستجو
          </button>
        </div>
        <div className="landing-search-fields">
          <label>
            شهر
            <input
              value={draft.city}
              onChange={(event) => update("city", event.target.value)}
              maxLength={80}
              placeholder={city}
            />
          </label>
          <label>
            محله
            <input
              value={draft.neighborhood}
              onChange={(event) => update("neighborhood", event.target.value)}
              maxLength={80}
              placeholder="همهٔ محله‌ها"
            />
          </label>
          <label>
            نوع ملک
            <select
              value={draft.property_type}
              onChange={(event) => update("property_type", event.target.value)}
            >
              <option value="">همهٔ انواع</option>
              {PROPERTY_TYPES.map((type) => (
                <option key={type} value={type}>
                  {PROPERTY_TYPE_LABELS[type]}
                </option>
              ))}
            </select>
          </label>
          <label>
            حداکثر قیمت یا رهن
            <select
              value={draft.max_price}
              onChange={(event) => update("max_price", event.target.value)}
            >
              <option value="">بدون سقف</option>
              {[
                500_000_000, 1_000_000_000, 3_000_000_000, 5_000_000_000, 10_000_000_000,
                20_000_000_000, 50_000_000_000, 100_000_000_000
              ].map((price) => (
                <option key={price} value={price}>
                  تا {toPersianDigits((price / 1_000_000_000).toLocaleString("en-US"))} میلیارد
                  تومان
                </option>
              ))}
            </select>
          </label>
          <label>
            حداقل متراژ
            <select
              value={draft.min_area}
              onChange={(event) => update("min_area", event.target.value)}
            >
              <option value="">هر متراژی</option>
              {[50, 80, 120, 150, 200, 300].map((area) => (
                <option key={area} value={area}>
                  از {toPersianDigits(String(area))} متر
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="landing-filter-footer">
          <p>بودجه برای فروش، قیمت کل و برای رهن و اجاره، مبلغ رهن است؛ مبالغ به تومان‌اند.</p>
          <button
            type="button"
            onClick={() => {
              setDraft(empty);
              setApplied(empty);
              setDeal("all");
              setShowcase("latest");
            }}
          >
            پاک‌کردن فیلترها
          </button>
        </div>
      </form>
      <div className="landing-showcase-toolbar">
        <div className="landing-showcase-tabs" role="group" aria-label="انتخاب ویترین">
          {showcases.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={showcase === item.id}
              onClick={() => setShowcase(item.id)}
            >
              {item.title}
            </button>
          ))}
        </div>
        <Link href="/">
          همهٔ آگهی‌ها <IconArrowUpLeft size={17} aria-hidden />
        </Link>
      </div>
      <div aria-live="polite" aria-busy={listings.isFetching}>
        {listings.isPending ? (
          <div className="landing-listings-grid" role="status" aria-label="در حال دریافت آگهی‌ها">
            {[0, 1, 2].map((index) => (
              <div key={index} className="landing-listing-skeleton" />
            ))}
          </div>
        ) : listings.isError ? (
          <div className="landing-listings-message" role="alert">
            <h3>{unauthorized ? "نمایش عمومی آگهی‌ها در دسترس نیست" : "دریافت آگهی‌ها ممکن نشد"}</h3>
            <p>
              {unauthorized
                ? "قرارداد فعلی سرویس، فهرست آگهی‌ها را به کاربران دارای دسترسی مجاز محدود می‌کند؛ ورود به‌تنهایی این مجوز را ایجاد نمی‌کند."
                : "ارتباط با فهرست املاک برقرار نشد؛ دوباره تلاش کنید."}
            </p>
            {!unauthorized && (
              <button
                className="landing-button landing-button-outline"
                type="button"
                onClick={() => void listings.refetch()}
              >
                تلاش دوباره
              </button>
            )}
          </div>
        ) : listings.data?.items.length ? (
          <>
            <p className="landing-showcase-count">
              نمایش {toPersianDigits(String(listings.data.items.length))} آگهی از{" "}
              {toPersianDigits(String(listings.data.count))} نتیجه
            </p>
            <div className="landing-listings-grid">
              {listings.data.items.map((property) => (
                <ListingCard
                  key={property.id}
                  property={property}
                  className="landing-listing-card"
                />
              ))}
            </div>
          </>
        ) : (
          <div className="landing-listings-message">
            <h3>آگهی منطبق پیدا نشد</h3>
            <p>
              شهر، بودجه یا سایر فیلترها را تغییر دهید. پوشش ویترین به آگهی‌های موجود سامانه وابسته
              است.
            </p>
          </div>
        )}
      </div>
      <p className="landing-data-note">
        قیمت‌ها قیمت پیشنهادی آگهی‌اند. نشان زیر قیمت بازار فقط برای فایل‌هایی نمایش داده می‌شود که
        سامانه آن‌ها را ارزش‌گذاری کرده است.
      </p>
    </section>
  );
}
