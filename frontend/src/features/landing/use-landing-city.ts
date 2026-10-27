"use client";

import { useEffect, useState } from "react";
import { useCityStore } from "@/store/useCityStore";

// Keep the landing picker on the same persisted city source as dashboard menus.
export const useLandingCityStore = useCityStore;

export function useLandingCity() {
  const activeCityName = useCityStore((state) => state.activeCity?.name ?? "تهران");
  const [city, setCity] = useState(activeCityName);
  useEffect(() => {
    setCity(activeCityName);
  }, [activeCityName]);
  useEffect(() => {
    const syncCity = (event: Event) => {
      const name = (event as CustomEvent<string>).detail;
      if (name) setCity(name);
    };
    window.addEventListener("shekarchi:city-changed", syncCity);
    return () => window.removeEventListener("shekarchi:city-changed", syncCity);
  }, []);
  return city;
}
