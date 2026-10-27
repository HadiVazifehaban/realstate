import * as React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LandingCityPicker } from "./components/landing-city-picker";
import { HeroMarket } from "./components/hero-market";
import { LandingListings } from "./components/landing-listings";
import { act } from "@testing-library/react";

const state = vi.hoisted(() => ({
  areas: vi.fn(),
  market: vi.fn(),
  listings: vi.fn(),
  active: null as string | null
}));
vi.mock("@/store/useCityStore", () => ({
  useCityStore: (selector: (value: { activeCity: { name: string } | null; setActiveCity: (city: { name: string }) => void }) => unknown) =>
    selector({
      activeCity: state.active ? { name: state.active } : null,
      setActiveCity: (city) => {
        state.active = city.name;
        localStorage.setItem("shekarchi_active_city", JSON.stringify(city));
      }
    })
}));
vi.mock("../use-landing-city", () => ({
  useLandingCity: () => state.active ?? "تهران"
}));
vi.mock("@/features/properties/api/client", async (original) => ({
  ...(await original<typeof import("@/features/properties/api/client")>()),
  fetchGisAreas: state.areas,
  fetchNeighbourhoodMarket: state.market,
  fetchProperties: state.listings
}));

function renderPicker(withData = false) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false, retryDelay: 0 } } })}
    >
      <LandingCityPicker />
      {withData && (
        <>
          <HeroMarket />
          <LandingListings />
        </>
      )}
    </QueryClientProvider>
  );
}

describe("landing city", () => {
  beforeEach(() => {
    localStorage.clear();
    state.active = null;
    state.areas.mockReset().mockResolvedValue({
      provinces: [
        { name: "تهران", cities: ["تهران", "دماوند"] },
        { name: "سیستان و بلوچستان", cities: ["چابهار"] }
      ]
    });
    state.market
      .mockReset()
      .mockResolvedValue({ items: [], count: 0, median_price_per_meter: null });
    state.listings.mockReset().mockResolvedValue({ items: [], count: 0 });
  });
  afterEach(cleanup);

  it("defaults the button and real data queries to Tehran, fetching provinces only when opened", async () => {
    renderPicker(true);
    expect(screen.getByRole("button", { name: /شهر فعلی: تهران/ })).toBeDefined();
    expect(state.areas).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(state.listings).toHaveBeenCalledWith(expect.objectContaining({ city: "تهران" }))
    );
    expect(state.market).toHaveBeenCalledWith(expect.objectContaining({ city: "تهران" }));
    fireEvent.click(screen.getByRole("button", { name: /شهر فعلی/ }));
    fireEvent.click(await screen.findByRole("button", { name: "چابهار" }));
    expect(screen.getByRole("button", { name: /شهر فعلی: چابهار/ })).toBeDefined();
    await waitFor(() =>
      expect(state.listings).toHaveBeenLastCalledWith(expect.objectContaining({ city: "چابهار" }))
    );
    expect(state.market).toHaveBeenLastCalledWith(expect.objectContaining({ city: "چابهار" }));
    expect(localStorage.getItem("shekarchi_active_city")).toContain("چابهار");
    expect(state.active).toBe("چابهار");
    act(() => window.dispatchEvent(new CustomEvent("shekarchi:city-changed", { detail: "رشت" })));
    expect(screen.getByRole("button", { name: /شهر فعلی: رشت/ })).toBeDefined();
  });

  it("preserves an existing active city and searches API cities by province", async () => {
    state.active = "شیراز";
    renderPicker();
    fireEvent.click(screen.getByRole("button", { name: /شهر فعلی: شیراز/ }));
    await screen.findByRole("button", { name: "چابهار" });
    fireEvent.change(screen.getByRole("textbox", { name: "جستجوی شهر یا استان" }), {
      target: { value: "سیستان" }
    });
    expect(screen.getByRole("button", { name: "چابهار" })).toBeDefined();
    expect(screen.queryByRole("button", { name: "دماوند" })).toBeNull();
  });

  it("shows errors with retry and an honest empty result", async () => {
    state.areas.mockRejectedValue(new Error("offline"));
    renderPicker();
    fireEvent.click(screen.getByRole("button", { name: /شهر فعلی/ }));
    expect(await screen.findByRole("alert")).toBeDefined();
    state.areas.mockResolvedValue({ provinces: [] });
    fireEvent.click(screen.getByRole("button", { name: "تلاش دوباره" }));
    expect(await screen.findByText("شهری پیدا نشد.")).toBeDefined();
  });
});
