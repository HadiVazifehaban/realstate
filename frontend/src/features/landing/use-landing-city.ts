"use client";

import { useEffect } from "react";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { useActiveCityName } from "@/store/useCityStore";

// Landing filters accept every API city, without inventing map coordinates.
export const useLandingCityStore = create<{
  city: string | null;
  setCity: (city: string) => void;
}>()(
  persist((set) => ({ city: null, setCity: (city) => set({ city }) }), {
    name: "shekarchi_landing_city",
    storage: createJSONStorage(() => localStorage),
    partialize: ({ city }) => ({ city }),
    skipHydration: true
  })
);

export function useLandingCity() {
  const city = useLandingCityStore((state) => state.city);
  const activeCity = useActiveCityName();
  useEffect(() => {
    if (!useLandingCityStore.persist.hasHydrated()) {
      void useLandingCityStore.persist.rehydrate();
    }
  }, []);
  return city ?? activeCity ?? "تهران";
}
