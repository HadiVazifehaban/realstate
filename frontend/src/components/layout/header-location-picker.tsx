"use client";

import React, { useState, useMemo } from "react";
import { Icons } from "@/components/icons";
import { useGisAreas, useInventoryCities } from "@/features/properties/hooks";
import { useQueryStates } from "nuqs";
import { parseAsArrayOf, parseAsString } from "nuqs";

interface CityNode {
  name: string;
  cities?: string[];
}

export default function HeaderLocationPicker({
  onLocationChange
}: {
  onLocationChange?: (cities: string[] | null) => void;
}) {
  const areasQuery = useGisAreas();
  const { data } = areasQuery;
  const inventoryQuery = useInventoryCities();

  const [isOpen, setIsOpen] = useState(false);
  const [selectedProvince, setSelectedProvince] = useState<CityNode | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // URL state for cities (syncs with BargainRadarPage)
  const [cityParams, setCityParams] = useQueryStates({
    city: parseAsArrayOf(parseAsString).withDefault([])
  });

  // Display name from URL params (primary) or global store (fallback)
  const activeCity =
    cityParams.city.length > 0
      ? cityParams.city.length === 1
        ? cityParams.city[0]
        : `${cityParams.city.length} شهر`
      : "همه شهرها";

  // Build tree from API data
  const tree = useMemo<CityNode[]>(() => {
    const provinces = (data?.provinces ?? []) as CityNode[];
    const known = new Set(
      provinces.flatMap((province) => (province.cities?.length ? province.cities : [province.name]))
    );
    const extra = (inventoryQuery.data?.cities ?? [])
      .filter((city: string) => !known.has(city))
      .map((city: string) => ({ name: city }));
    return [...provinces, ...extra];
  }, [data, inventoryQuery.data]);

  const IRAN_PROVINCES = tree;

  // Extract popular cities from inventory
  const POPULAR_CITIES = useMemo(() => {
    const allCities = IRAN_PROVINCES.flatMap((p) => p.cities || [p.name]);
    const popular = ["تهران", "کرج", "مشهد", "اصفهان", "شیراز", "تبریز", "رشت"];
    return popular.filter((c) => allCities.includes(c));
  }, [IRAN_PROVINCES]);

  // فیلتر جستجو
  const filteredList = useMemo(() => {
    if (!searchQuery.trim()) return null;
    const q = searchQuery.trim().toLowerCase();

    const results: { province: string; city: string }[] = [];
    IRAN_PROVINCES.forEach((prov) => {
      const cities = prov.cities?.length ? prov.cities : [prov.name];
      cities.forEach((c) => {
        if (c.includes(q) || prov.name.includes(q)) {
          results.push({ province: prov.name, city: c });
        }
      });
    });
    return results;
  }, [searchQuery, IRAN_PROVINCES]);

  const handleSelectAllCities = () => {
    setIsOpen(false);
    setCityParams({ city: [] });
    onLocationChange?.(null);
  };

  const handleSelectAllCitiesInCountry = () => {
    handleSelectAllCities();
  };

  const handleToggleCity = (city: string, _provinceName?: string) => {
    const currentCities = cityParams.city;
    const isSelected = currentCities.includes(city);

    let newCities: string[];
    if (isSelected) {
      newCities = currentCities.filter((c) => c !== city);
    } else {
      newCities = [...currentCities, city];
    }

    setCityParams({ city: newCities });
    onLocationChange?.(newCities.length ? newCities : null);
    setIsOpen(false);
    setSelectedProvince(null);
    setSearchQuery("");

  };

  const handleSelectProvince = (province: CityNode) => {
    setSelectedProvince(province);
  };

  const handleToggleAllCitiesInProvince = (province: CityNode) => {
    const cities = province.cities || [province.name];
    const currentCities = cityParams.city;

    // Check if all cities in province are already selected
    const allSelected = cities.every((c) => currentCities.includes(c));

    let newCities: string[];
    let citiesToAdd: string[] = [];

    if (allSelected) {
      // Deselect all cities in this province
      newCities = currentCities.filter((c) => !cities.includes(c));
    } else {
      // Select all cities in this province
      citiesToAdd = cities.filter((c) => !currentCities.includes(c));
      newCities = [...currentCities, ...citiesToAdd];
    }

    setCityParams({ city: newCities });
    onLocationChange?.(newCities.length ? newCities : null);

  };

  return (
    <div className="header-location-picker relative inline-block text-right font-['Vazirmatn']" dir="rtl">
      {/* دکمه کپسولی هدر (Trigger) */}
      <button
        type="button"
        aria-label="انتخاب شهر و استان"
        aria-expanded={isOpen}
        onClick={() => setIsOpen(!isOpen)}
        className="header-location-trigger flex items-center gap-2 px-3 text-xs shadow-inner focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      >
        <Icons.mapPin className="w-3.5 h-3.5 text-primary" />
        <span className="header-location-name max-w-32 truncate font-medium text-inherit">{activeCity}</span>
        <Icons.chevronDown
          className={`w-3.5 h-3.5 text-muted-foreground transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
        />
      </button>

      {/* دراپ‌داون شیشه‌ای انتخاب شهر و استان */}
      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-xs"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute left-0 mt-2 w-84 z-50 rounded-2xl bg-[var(--brand-0b1019)]/95 backdrop-blur-xl border border-foreground/10 shadow-2xl shadow-black/80 p-3 text-right">
            {/* سرچ بار و دکمه بستن */}
            <div className="relative mb-2.5">
              <input
                type="text"
                placeholder="جستجوی شهر یا استان..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-[var(--brand-141b27)] border border-foreground/10 rounded-xl px-8 py-2 text-xs text-foreground placeholder-gray-400 focus:outline-none focus:border-primary/60 transition"
              />
              <Icons.search className="w-3.5 h-3.5 text-muted-foreground absolute right-2.5 top-2.5" />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute left-2.5 top-2.5 text-muted-foreground hover:text-foreground"
                >
                  <Icons.close className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {areasQuery.isPending && (
              <p role="status" className="mb-3 text-xs text-muted-foreground">
                در حال دریافت استان‌ها و شهرها…
              </p>
            )}
            {(areasQuery.isError || (!areasQuery.isPending && !data?.provinces?.length)) && (
              <div
                role="status"
                className="mb-3 space-y-2 rounded-lg border border-amber-400/20 p-2 text-xs text-amber-200"
              >
                <p>
                  فهرست کامل استان‌ها و شهرها دریافت نشد؛ فقط شهرهای فایل‌های موجود نمایش داده می‌شوند.
                </p>
                <button
                  type="button"
                  disabled={areasQuery.isFetching}
                  onClick={() => void areasQuery.refetch()}
                  className="underline disabled:opacity-50"
                >
                  تلاش دوباره
                </button>
              </div>
            )}

            {/* دسترسی سریع به «سراسر کشور» و شهرهای محبوب */}
            {!searchQuery && !selectedProvince && (
              <div className="mb-3 pb-2.5 border-b border-foreground/5">
                <div className="flex gap-2 mb-2">
                  <button
                    onClick={handleSelectAllCities}
                    className={`flex-1 flex items-center justify-center gap-2 p-2 rounded-xl text-xs transition ${
                      cityParams.city.length === 0
                        ? "bg-[var(--brand-e5a87b)]/15 text-primary border border-primary/30"
                        : "bg-[var(--brand-141b27)]/60 text-gray-300 hover:bg-[var(--brand-1a2332)]"
                    }`}
                  >
                    <Icons.home className="w-3.5 h-3.5 text-primary" />
                    <span>هیچ‌کدام</span>
                  </button>
                  <button
                    onClick={handleSelectAllCitiesInCountry}
                    className={`flex-1 flex items-center justify-center gap-2 p-2 rounded-xl text-xs transition ${
                      IRAN_PROVINCES.flatMap((p) => p.cities || [p.name]).every((c) =>
                        cityParams.city.includes(c)
                      )
                        ? "bg-[var(--brand-e5a87b)]/15 text-primary border border-primary/30"
                        : "bg-[var(--brand-141b27)]/60 text-gray-300 hover:bg-[var(--brand-1a2332)]"
                    }`}
                  >
                    <Icons.home className="w-3.5 h-3.5 text-primary" />
                    <span>همه شهرها</span>
                  </button>
                </div>

                <div className="flex flex-wrap gap-1.5">
                  {POPULAR_CITIES.map((c) => (
                    <button
                      key={c}
                      onClick={() => handleToggleCity(c)}
                      className={`text-[11px] px-2.5 py-1 rounded-lg border transition ${
                        cityParams.city.includes(c)
                          ? "bg-[var(--brand-e5a87b)]/20 border-primary/50 text-primary"
                          : "border-foreground/5 bg-[var(--brand-121824)]/60 text-muted-foreground hover:text-foreground hover:border-foreground/20"
                      }`}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* بدنه لیست: حالت نتایج جستجو */}
            {searchQuery ? (
              <div className="max-h-60 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
                {filteredList && filteredList.length > 0 ? (
                  filteredList.map((item, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleToggleCity(item.city, item.province)}
                      className={`w-full flex items-center justify-between p-2 rounded-lg text-xs transition ${
                        cityParams.city.includes(item.city)
                          ? "bg-[var(--brand-e5a87b)]/15 text-primary"
                          : "text-gray-300 hover:bg-[var(--brand-1a2332)] hover:text-foreground"
                      }`}
                    >
                      <span>{item.city}</span>
                      <span className="text-[10px] text-muted-foreground">{item.province}</span>
                      {cityParams.city.includes(item.city) && (
                        <Icons.check className="w-3.5 h-3.5 text-primary" />
                      )}
                    </button>
                  ))
                ) : (
                  <div className="py-6 text-center text-xs text-muted-foreground">
                    شهری با این نام یافت نشد
                  </div>
                )}
              </div>
            ) : selectedProvince ? (
              /* بدنه لیست: حالت نمایش شهرستان‌های استان انتخابی */
              <div>
                <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-foreground/5">
                  <button
                    onClick={() => setSelectedProvince(null)}
                    className="flex items-center gap-1.5 text-xs text-primary hover:text-primary transition"
                  >
                    <Icons.chevronLeft className="w-3.5 h-3.5" />
                    <span>بازگشت به استان‌ها</span>
                  </button>
                  <span className="text-xs text-muted-foreground font-medium">{selectedProvince.name}</span>
                </div>

                <div className="max-h-56 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
                  <button
                    onClick={() => handleToggleAllCitiesInProvince(selectedProvince)}
                    className={`w-full flex items-center justify-between p-2 rounded-lg text-xs transition ${
                      (selectedProvince.cities || [selectedProvince.name]).every((c) =>
                        cityParams.city.includes(c)
                      )
                        ? "bg-[var(--brand-e5a87b)]/15 text-primary"
                        : "text-gray-300 hover:bg-[var(--brand-1a2332)] hover:text-foreground"
                    }`}
                  >
                    <span className="font-semibold text-foreground">
                      همه شهرهای {selectedProvince.name}
                    </span>
                    {(selectedProvince.cities || [selectedProvince.name]).every((c) =>
                      cityParams.city.includes(c)
                    ) && <Icons.check className="w-3.5 h-3.5 text-primary" />}
                  </button>
                  {(selectedProvince.cities || [selectedProvince.name]).map((city) => (
                    <button
                      key={city}
                      onClick={() => handleToggleCity(city, selectedProvince.name)}
                      className={`w-full flex items-center justify-between p-2 rounded-lg text-xs transition ${
                        cityParams.city.includes(city)
                          ? "bg-[var(--brand-e5a87b)]/15 text-primary"
                          : "text-gray-300 hover:bg-[var(--brand-1a2332)] hover:text-foreground"
                      }`}
                    >
                      <span>{city}</span>
                      {cityParams.city.includes(city) && (
                        <Icons.check className="w-3.5 h-3.5 text-primary" />
                      )}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              /* بدنه لیست: حالت انتخاب استان */
              <div>
                <div className="text-[11px] text-muted-foreground mb-1 px-1">انتخاب استان:</div>
                <div className="max-h-56 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
                  {IRAN_PROVINCES.map((prov) => {
                    const cities = prov.cities?.length ? prov.cities : [prov.name];
                    const allSelected = cities.every((c) => cityParams.city.includes(c));
                    const someSelected = cities.some((c) => cityParams.city.includes(c));
                    return (
                      <div key={prov.name} className="flex items-center gap-2">
                        <button
                          onClick={() => handleToggleAllCitiesInProvince(prov)}
                          className={`flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-lg text-xs transition ${
                            allSelected
                              ? "bg-[var(--brand-e5a87b)]/20 text-primary"
                              : someSelected
                                ? "bg-[var(--brand-e5a87b)]/10 text-primary"
                                : "bg-[var(--brand-141b27)]/60 text-muted-foreground hover:text-foreground"
                          }`}
                        >
                          {allSelected ? (
                            <Icons.check className="w-3.5 h-3.5" />
                          ) : (
                            <Icons.chevronRight className="w-3.5 h-3.5" />
                          )}
                        </button>
                        <button
                          onClick={() => handleSelectProvince(prov)}
                          className="flex-1 flex items-center justify-between p-2 rounded-lg text-xs text-gray-300 hover:bg-[var(--brand-1a2332)] hover:text-foreground transition group"
                        >
                          <span>{prov.name}</span>
                          <span className="text-[10px] text-muted-foreground group-hover:text-gray-300">
                            {cities.length} شهر ←
                          </span>
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
