"use client";

import React, { useState, useMemo } from "react";
import { Icons } from '@/components/icons';
import { useGisAreas, useInventoryCities } from '@/features/properties/hooks';
import { useCityStore, useActiveCityName } from '@/store/useCityStore';
import { findCityByName, type ShekarchiCity } from '@/constants/cities';
import { useQueryStates } from 'nuqs';
import { parseAsArrayOf, parseAsString } from 'nuqs';

interface CityNode {
  name: string;
  cities?: string[];
}

export default function HeaderLocationPicker({ 
  onLocationChange 
}: { 
  onLocationChange?: (cities: string[] | null) => void 
}) {
  const { data } = useGisAreas();
  const inventoryQuery = useInventoryCities();
  const activeCityName = useActiveCityName();
  const setActiveCity = useCityStore((state) => state.setActiveCity);
  
  const [isOpen, setIsOpen] = useState(false);
  const [selectedProvince, setSelectedProvince] = useState<CityNode | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // URL state for cities (syncs with BargainRadarPage)
  const [cityParams, setCityParams] = useQueryStates({
    city: parseAsArrayOf(parseAsString).withDefault([])
  });

  // Display name from URL params (primary) or global store (fallback)
  const activeCity = cityParams.city.length > 0 
    ? (cityParams.city.length === 1 ? cityParams.city[0] : `${cityParams.city.length} شهر`)
    : (activeCityName || "همه شهرها");

  // Build tree from API data
  const tree = useMemo<CityNode[]>(() => {
    const provinces = (data?.provinces ?? []) as CityNode[];
    const known = new Set(provinces.flatMap((province) => province.cities?.length ? province.cities : [province.name]));
    const extra = (inventoryQuery.data?.cities ?? [])
      .filter((city: string) => !known.has(city))
      .map((city: string) => ({ name: city }));
    return [...provinces, ...extra];
  }, [data, inventoryQuery.data]);

  const IRAN_PROVINCES = tree;
  
  // Extract popular cities from inventory
  const POPULAR_CITIES = useMemo(() => {
    const allCities = IRAN_PROVINCES.flatMap(p => p.cities || [p.name]);
    const popular = ["تهران", "کرج", "مشهد", "اصفهان", "شیراز", "تبریز", "رشت"];
    return popular.filter(c => allCities.includes(c));
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
  };

  const handleSelectAllCitiesInCountry = () => {
    const allCities = IRAN_PROVINCES.flatMap(p => p.cities || [p.name]);
    setCityParams({ city: allCities });
  };

  const triggerCityScrape = async (city: string) => {
    try {
      await fetch('/api/v1/scraper/set-focus-city', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ city }),
      });
    } catch (err) {
      console.error('Failed to trigger city scrape:', err);
    }
  };

  const handleToggleCity = (city: string, provinceName?: string) => {
    const currentCities = cityParams.city;
    const isSelected = currentCities.includes(city);
    
    let newCities: string[];
    if (isSelected) {
      newCities = currentCities.filter(c => c !== city);
    } else {
      newCities = [...currentCities, city];
    }
    
    // Update global city store if single city is in ShekarchiCity list
    if (newCities.length === 1) {
      const shekarchiCity = findCityByName(newCities[0]);
      if (shekarchiCity) {
        setActiveCity(shekarchiCity);
      }
    }
    
    setCityParams({ city: newCities });
    
    // Trigger scraper for the selected city
    triggerCityScrape(city);
  };

  const handleSelectProvince = (province: CityNode) => {
    setSelectedProvince(province);
  };

  const handleToggleAllCitiesInProvince = (province: CityNode) => {
    const cities = province.cities || [province.name];
    const currentCities = cityParams.city;
    
    // Check if all cities in province are already selected
    const allSelected = cities.every(c => currentCities.includes(c));
    
    let newCities: string[];
    let citiesToAdd: string[] = [];
    
    if (allSelected) {
      // Deselect all cities in this province
      newCities = currentCities.filter(c => !cities.includes(c));
    } else {
      // Select all cities in this province
      citiesToAdd = cities.filter(c => !currentCities.includes(c));
      newCities = [...currentCities, ...citiesToAdd];
    }
    
    setCityParams({ city: newCities });
    
    // Trigger scraper for newly selected cities
    if (!allSelected) {
      citiesToAdd.forEach(city => triggerCityScrape(city));
    }
  };

  return (
    <div className="relative inline-block text-right font-['Vazirmatn']" dir="rtl">
      {/* دکمه کپسولی هدر (Trigger) */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#121824]/80 hover:bg-[#1a2332] text-gray-200 border border-white/10 hover:border-[#ffd8be]/40 transition-all duration-200 text-xs shadow-inner"
      >
        <Icons.mapPin className="w-3.5 h-3.5 text-[#e5a87b]" />
        <span className="font-medium text-white">{activeCity}</span>
        <Icons.chevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} />
      </button>

      {/* دراپ‌داون شیشه‌ای انتخاب شهر و استان */}
      {isOpen && (
        <>
          <div 
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-xs" 
            onClick={() => setIsOpen(false)} 
          />
          <div className="absolute left-0 mt-2 w-84 z-50 rounded-2xl bg-[#0b1019]/95 backdrop-blur-xl border border-white/10 shadow-2xl shadow-black/80 p-3 text-right">
            
            {/* سرچ بار و دکمه بستن */}
            <div className="relative mb-2.5">
              <input
                type="text"
                placeholder="جستجوی شهر یا استان..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-[#141b27] border border-white/10 rounded-xl px-8 py-2 text-xs text-white placeholder-gray-400 focus:outline-none focus:border-[#e5a87b]/60 transition"
              />
              <Icons.search className="w-3.5 h-3.5 text-gray-400 absolute right-2.5 top-2.5" />
              {searchQuery && (
                <button 
                  onClick={() => setSearchQuery("")}
                  className="absolute left-2.5 top-2.5 text-gray-400 hover:text-white"
                >
                  <Icons.close className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* دسترسی سریع به «سراسر کشور» و شهرهای محبوب */}
            {!searchQuery && !selectedProvince && (
              <div className="mb-3 pb-2.5 border-b border-white/5">
                <div className="flex gap-2 mb-2">
                  <button
                    onClick={handleSelectAllCities}
                    className={`flex-1 flex items-center justify-center gap-2 p-2 rounded-xl text-xs transition ${
                      cityParams.city.length === 0 
                        ? "bg-[#e5a87b]/15 text-[#ffd8be] border border-[#e5a87b]/30" 
                        : "bg-[#141b27]/60 text-gray-300 hover:bg-[#1a2332]"
                    }`}
                  >
                    <Icons.home className="w-3.5 h-3.5 text-[#e5a87b]" />
                    <span>هیچ‌کدام</span>
                  </button>
                  <button
                    onClick={handleSelectAllCitiesInCountry}
                    className={`flex-1 flex items-center justify-center gap-2 p-2 rounded-xl text-xs transition ${
                      IRAN_PROVINCES.flatMap(p => p.cities || [p.name]).every(c => cityParams.city.includes(c))
                        ? "bg-[#e5a87b]/15 text-[#ffd8be] border border-[#e5a87b]/30" 
                        : "bg-[#141b27]/60 text-gray-300 hover:bg-[#1a2332]"
                    }`}
                  >
                    <Icons.home className="w-3.5 h-3.5 text-[#e5a87b]" />
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
                          ? "bg-[#e5a87b]/20 border-[#e5a87b]/50 text-[#ffd8be]"
                          : "border-white/5 bg-[#121824]/60 text-gray-400 hover:text-white hover:border-white/20"
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
                          ? "bg-[#e5a87b]/15 text-[#ffd8be]" 
                          : "text-gray-300 hover:bg-[#1a2332] hover:text-white"
                      }`}
                    >
                      <span>{item.city}</span>
                      <span className="text-[10px] text-gray-400">{item.province}</span>
                      {cityParams.city.includes(item.city) && <Icons.check className="w-3.5 h-3.5 text-[#e5a87b]" />}
                    </button>
                  ))
                ) : (
                  <div className="py-6 text-center text-xs text-gray-400">
                    شهری با این نام یافت نشد
                  </div>
                )}
              </div>
            ) : selectedProvince ? (
              /* بدنه لیست: حالت نمایش شهرستان‌های استان انتخابی */
              <div>
                <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-white/5">
                  <button
                    onClick={() => setSelectedProvince(null)}
                    className="flex items-center gap-1.5 text-xs text-[#e5a87b] hover:text-[#ffd8be] transition"
                  >
                    <Icons.chevronLeft className="w-3.5 h-3.5" />
                    <span>بازگشت به استان‌ها</span>
                  </button>
                  <span className="text-xs text-gray-400 font-medium">{selectedProvince.name}</span>
                </div>

                <div className="max-h-56 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
                  <button
                    onClick={() => handleToggleAllCitiesInProvince(selectedProvince)}
                    className={`w-full flex items-center justify-between p-2 rounded-lg text-xs transition ${
                      (selectedProvince.cities || [selectedProvince.name]).every(c => cityParams.city.includes(c))
                        ? "bg-[#e5a87b]/15 text-[#ffd8be]" 
                        : "text-gray-300 hover:bg-[#1a2332] hover:text-white"
                    }`}
                  >
                    <span className="font-semibold text-white">همه شهرهای {selectedProvince.name}</span>
                    {(selectedProvince.cities || [selectedProvince.name]).every(c => cityParams.city.includes(c)) && <Icons.check className="w-3.5 h-3.5 text-[#e5a87b]" />}
                  </button>
                  {(selectedProvince.cities || [selectedProvince.name]).map((city) => (
                    <button
                      key={city}
                      onClick={() => handleToggleCity(city, selectedProvince.name)}
                      className={`w-full flex items-center justify-between p-2 rounded-lg text-xs transition ${
                        cityParams.city.includes(city)
                          ? "bg-[#e5a87b]/15 text-[#ffd8be]" 
                          : "text-gray-300 hover:bg-[#1a2332] hover:text-white"
                      }`}
                    >
                      <span>{city}</span>
                      {cityParams.city.includes(city) && <Icons.check className="w-3.5 h-3.5 text-[#e5a87b]" />}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              /* بدنه لیست: حالت انتخاب استان */
              <div>
                <div className="text-[11px] text-gray-400 mb-1 px-1">انتخاب استان:</div>
                <div className="max-h-56 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
                  {IRAN_PROVINCES.map((prov) => {
                    const cities = prov.cities?.length ? prov.cities : [prov.name];
                    const allSelected = cities.every(c => cityParams.city.includes(c));
                    const someSelected = cities.some(c => cityParams.city.includes(c));
                    return (
                      <div key={prov.name} className="flex items-center gap-2">
                        <button
                          onClick={() => handleToggleAllCitiesInProvince(prov)}
                          className={`flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-lg text-xs transition ${
                            allSelected
                              ? "bg-[#e5a87b]/20 text-[#ffd8be]" 
                              : someSelected
                              ? "bg-[#e5a87b]/10 text-[#ffd8be]"
                              : "bg-[#141b27]/60 text-gray-400 hover:text-white"
                          }`}
                        >
                          {allSelected ? <Icons.check className="w-3.5 h-3.5" /> : <Icons.chevronRight className="w-3.5 h-3.5" />}
                        </button>
                        <button
                          onClick={() => handleSelectProvince(prov)}
                          className="flex-1 flex items-center justify-between p-2 rounded-lg text-xs text-gray-300 hover:bg-[#1a2332] hover:text-white transition group"
                        >
                          <span>{prov.name}</span>
                          <span className="text-[10px] text-gray-400 group-hover:text-gray-300">
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
