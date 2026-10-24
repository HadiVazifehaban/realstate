"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Icons } from "@/components/icons";
import { mediaUrl } from "@/lib/media-url";
import { formatPricePerMeter, toPersianDigits } from "@/lib/utils";
import type { NeighbourhoodStat } from "../types";

const FAVORITES_KEY = "shekarchi:market-neighbourhood-favorites";

function readFavorites(): string[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(FAVORITES_KEY) ?? "[]");
    return Array.isArray(value) ? value.filter((id): id is string => typeof id === "string") : [];
  } catch {
    return [];
  }
}

export function SelectedNeighbourhoodCard({
  row,
  photo,
  compact = false,
  vertical = false
}: {
  row: NeighbourhoodStat;
  photo?: string | null;
  compact?: boolean;
  vertical?: boolean;
}) {
  const id = JSON.stringify([row.city, row.neighborhood]);
  const [favorite, setFavorite] = React.useState(false);
  const [notice, setNotice] = React.useState("");
  const [failedPhoto, setFailedPhoto] = React.useState<string | null>(null);

  React.useEffect(() => {
    setFavorite(readFavorites().includes(id));
  }, [id]);

  const toggleFavorite = () => {
    try {
      const saved = readFavorites();
      const exists = saved.includes(id);
      localStorage.setItem(
        FAVORITES_KEY,
        JSON.stringify(exists ? saved.filter((item) => item !== id) : [...saved, id])
      );
      setFavorite(!exists);
      setNotice(
        exists ? "از علاقه‌مندی‌های این مرورگر حذف شد." : "در علاقه‌مندی‌های این مرورگر ذخیره شد."
      );
    } catch {
      setNotice("ذخیرهٔ علاقه‌مندی در این مرورگر ممکن نیست.");
    }
  };

  if (compact) {
    return (
      <section
        aria-label={`تحلیل محلهٔ ${row.neighborhood}`}
        dir="rtl"
        className={`flex w-full min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-xl border border-gold-accent/30 bg-[#060b13]/90 px-4 py-2.5 text-xs text-gray-300 ${vertical ? "avm-district-vertical" : ""}`}
      >
        <h2 className="min-w-0 break-words font-bold text-gold-primary">{row.neighborhood}</h2>
        <p title="شاخص ارائه‌شده توسط API میانه است، نه میانگین.">
          میانهٔ متراژ:{" "}
          <strong className="text-gold-primary">
            {row.median_area == null
              ? "—"
              : `${toPersianDigits(row.median_area.toLocaleString("en-US"))} متر`}
          </strong>
        </p>
        <p>
          قیمت هر متر:{" "}
          <strong className="text-gold-primary">
            {row.median_price_per_meter == null
              ? "—"
              : formatPricePerMeter(row.median_price_per_meter)}
          </strong>
        </p>
        <Button
          variant="ghost"
          size="sm"
          aria-pressed={favorite}
          onClick={toggleFavorite}
          title="ذخیره فقط در همین مرورگر"
          className="h-7 px-2 text-[10px] text-gold-primary"
        >
          {favorite ? "حذف از علاقه‌مندی‌ها" : "افزودن به علاقه‌مندی‌ها"}
        </Button>
        <p role="status" className="sr-only">
          {notice}
        </p>
      </section>
    );
  }

  return (
    <section
      aria-label={`تحلیل محلهٔ ${row.neighborhood}`}
      dir="rtl"
      className="relative isolate grid w-full min-w-0 items-center gap-3 rounded-2xl border border-gold-accent/30 bg-[linear-gradient(135deg,rgba(22,27,35,0.95),rgba(9,12,18,0.9))] p-3 text-right text-[#f5f5f7] shadow-lg backdrop-blur-xl lg:min-h-32 lg:grid-cols-2"
    >
      <div className="flex min-w-0 items-center gap-3" data-testid="neighbourhood-description">
        <div className="flex h-16 w-20 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-gold-accent/20 bg-white/5">
          {photo && failedPhoto !== photo ? (
            // This is a real listing photo, not an invented neighbourhood image.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={mediaUrl(photo)}
              alt={`تصویر یکی از املاک ${row.neighborhood}`}
              className="size-full object-cover"
              onError={() => setFailedPhoto(photo)}
            />
          ) : (
            <Icons.mapPin aria-label="تصویر محله موجود نیست" className="size-8 text-gold-primary" />
          )}
        </div>
        <div className="min-w-0 space-y-1">
          <h2 className="truncate text-base font-bold text-gold-primary" title={row.neighborhood}>
            {row.neighborhood}
          </h2>
          <p className="text-xs text-[#94a3b8]">{row.city || "شهر نامشخص"}</p>
          <p
            className="line-clamp-1 text-xs leading-5 text-[#cbd5e1]"
            title={`تحلیل بر پایهٔ ${toPersianDigits(String(row.files))} فایل قیمت‌دار از ${toPersianDigits(String(row.all_files))} فایل؛ میانهٔ قیمت‌های ثبت‌شده، نه قیمت قطعی معاملات.`}
          >
            تحلیل بر پایهٔ {toPersianDigits(String(row.files))} فایل قیمت‌دار از{" "}
            {toPersianDigits(String(row.all_files))} فایل این محله است. قیمت‌ها میانهٔ فایل‌های
            ثبت‌شده‌اند، نه قیمت قطعی معاملات.
          </p>
        </div>
      </div>

      <dl className="grid min-w-0 grid-cols-2 gap-2" data-testid="neighbourhood-metrics">
        <Metric
          label="قیمت هر متر مربع"
          value={
            row.median_price_per_meter == null
              ? "—"
              : formatPricePerMeter(row.median_price_per_meter)
          }
          note="تومان · میانهٔ فایل‌ها"
        />
        <Metric
          label="متوسط متراژ ملک"
          value={
            row.median_area == null
              ? "—"
              : `${toPersianDigits(row.median_area.toLocaleString("en-US"))} متر مربع`
          }
          note="شاخص موجود: میانهٔ متراژ، نه میانگین"
        />
        <Metric label="رشد قیمت" value="—" note="دادهٔ تاریخی موجود نیست" />
        <Metric label="تراکم ساخت" value="—" note="دادهٔ تراکم ساخت موجود نیست" />
      </dl>

      <div className="flex min-w-0 flex-col justify-center gap-1 lg:col-span-2">
        <Button
          variant="outline"
          aria-pressed={favorite}
          onClick={toggleFavorite}
          className="h-auto min-h-10 w-full whitespace-normal border-gold-accent/40 bg-white/5 px-3 py-2 text-gold-primary hover:bg-white/10"
        >
          {favorite ? "حذف از علاقه‌مندی‌ها" : "افزودن به علاقه‌مندی‌ها"}
        </Button>
        <p className="text-[10px] leading-5 text-[#94a3b8]">ذخیره فقط در همین مرورگر</p>
        <p role="status" className="text-[10px] leading-4 text-gold-primary">
          {notice}
        </p>
      </div>
    </section>
  );
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-gold-accent/15 bg-white/5 p-2 backdrop-blur-md">
      <dt className="truncate text-[10px] text-[#94a3b8]" title={label}>
        {label}
      </dt>
      <dd className="mt-1 truncate text-xs font-bold tabular-nums text-gold-primary" title={value}>
        {value}
      </dd>
      <dd className="mt-1 truncate text-[9px] leading-4 text-[#94a3b8]" title={note}>
        {note}
      </dd>
    </div>
  );
}
