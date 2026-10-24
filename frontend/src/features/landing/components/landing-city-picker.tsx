"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { IconMapPin, IconChevronDown } from "@tabler/icons-react";
import { fetchGisAreas } from "@/features/properties/api/client";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { useLandingCity, useLandingCityStore } from "../use-landing-city";

const normalize = (text: string) =>
  text
    .replace(/[يى]/g, "ی")
    .replace(/ك/g, "ک")
    .trim();

export function LandingCityPicker() {
  const city = useLandingCity();
  const setCity = useLandingCityStore((state) => state.setCity);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const areas = useQuery({
    queryKey: ["gis", "areas"],
    queryFn: fetchGisAreas,
    enabled: open,
    staleTime: 86_400_000,
    retry: 1
  });
  const provinces = useMemo(() => {
    const query = normalize(search);
    return (areas.data?.provinces ?? [])
      .map((province) => ({
        ...province,
        cities: province.cities.filter(
          (name) => normalize(name).includes(query) || normalize(province.name).includes(query)
        )
      }))
      .filter((province) => province.cities.length > 0);
  }, [areas.data, search]);

  return (
    <>
      <button
        type="button"
        className="landing-button landing-button-glass landing-city-trigger"
        aria-label={`شهر فعلی: ${city}؛ تغییر شهر و استان`}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => {
          setSearch("");
          setOpen(true);
        }}
      >
        <IconMapPin size={20} aria-hidden />
        <span>
          شهر فعلی: <strong>{city}</strong>
        </span>
        <IconChevronDown size={16} aria-hidden />
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent dir="rtl" className="landing-city-dialog">
          <DialogTitle>انتخاب شهر و استان</DialogTitle>
          <DialogDescription>
            آگهی‌ها و تحلیل‌های لندینگ بر اساس این شهر نمایش داده می‌شوند.
          </DialogDescription>
          <input
            className="landing-city-search"
            aria-label="جستجوی شهر یا استان"
            placeholder="جستجوی شهر یا استان…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <div className="landing-city-options">
            {areas.isPending && <p role="status">در حال دریافت استان‌ها و شهرها…</p>}
            {areas.isError && (
              <div role="alert">
                <p>فهرست استان‌ها و شهرها دریافت نشد.</p>
                <button type="button" onClick={() => void areas.refetch()}>
                  تلاش دوباره
                </button>
              </div>
            )}
            {provinces.map((province) => (
              <section key={province.name} aria-label={province.name}>
                <h3>{province.name}</h3>
                <div>
                  {province.cities.map((name) => (
                    <button
                      type="button"
                      key={name}
                      aria-pressed={city === name}
                      onClick={() => {
                        setCity(name);
                        setOpen(false);
                      }}
                    >
                      {name}
                    </button>
                  ))}
                </div>
              </section>
            ))}
            {areas.isSuccess && provinces.length === 0 && <p role="status">شهری پیدا نشد.</p>}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
