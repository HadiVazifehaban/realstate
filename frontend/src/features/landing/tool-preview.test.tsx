import * as React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
const state = vi.hoisted(() => ({ city: "رشت" as string | null }));
vi.mock("@/store/useCityStore", () => ({ useActiveCityName: () => state.city }));
vi.mock("@/features/properties/api/client", () => ({
  ApiError: class extends Error {
    constructor(public status: number) {
      super("failed");
    }
  },
  fetchNeighbourhoodMarket: vi.fn(),
  fetchBargains: vi.fn()
}));
import {
  ApiError,
  fetchBargains,
  fetchNeighbourhoodMarket
} from "@/features/properties/api/client";
import { ToolPreview, projectLocations } from "./components/tool-preview";
import { HeroOpportunity } from "./components/hero-opportunity";
import { HeroMarket } from "./components/hero-market";
const row = {
  city: "رشت",
  neighborhood: "گلسار",
  median_price_per_meter: 98765432,
  latitude: 37.3,
  longitude: 49.6,
  all_files: 7
};
function view(kind: "chart" | "map" | "radar") {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}
    >
      <ToolPreview kind={kind} />
    </QueryClientProvider>
  );
}
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  state.city = "رشت";
});
function hero() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}
    >
      <HeroOpportunity />
    </QueryClientProvider>
  );
}
it("renders the floating opportunity using actual property fields and AVM ratio", async () => {
  vi.mocked(fetchBargains).mockResolvedValue({
    items: [
      {
        id: "real",
        property_type: "APARTMENT",
        area: 93,
        neighborhood: "گلسار",
        city: "رشت",
        valuation_status: "BARGAIN",
        valuation_deviation_pct: -17.25
      }
    ]
  } as never);
  const { container } = hero();
  await screen.findByText("۱۷٫۲۵٪ کمتر").catch(() => screen.findByText("۱۷.۲۵٪ کمتر"));
  expect(screen.getByText(/آپارتمان ۹۳ متری · گلسار · رشت/)).toBeTruthy();
  expect(
    (container.querySelector(".landing-opportunity-track span") as HTMLElement).style.width
  ).toBe("82.75%");
  expect(fetchBargains).toHaveBeenCalledWith({ city: "رشت", limit: 30 });
  expect(container.textContent).not.toMatch(/۱۸۵|زعفرانیه|همین حالا/);
});
it("does not fabricate an opportunity on an empty radar", async () => {
  vi.mocked(fetchBargains).mockResolvedValue({ items: [], count: 0 });
  const { container } = hero();
  await waitFor(() => expect(fetchBargains).toHaveBeenCalled());
  await screen.findByText("فرصت دارای ارزش‌گذاری معتبر در داده‌های فعلی یافت نشد.");
  expect(container.querySelector(".landing-opportunity-track")).toBeNull();
});
it("rejects missing or contradictory AVM deviations", async () => {
  vi.mocked(fetchBargains).mockResolvedValue({
    items: [
      { valuation_status: "BARGAIN", valuation_deviation_pct: null },
      { valuation_status: "BARGAIN", valuation_deviation_pct: 12 }
    ]
  } as never);
  const { container } = hero();
  await waitFor(() => expect(fetchBargains).toHaveBeenCalled());
  await screen.findByText("فرصت دارای ارزش‌گذاری معتبر در داده‌های فعلی یافت نشد.");
  expect(container.querySelector(".landing-opportunity-track")).toBeNull();
});
it("renders server medians, not invented growth or historical trends, and scopes to active city", async () => {
  vi.mocked(fetchNeighbourhoodMarket).mockResolvedValue({
    items: [row],
    median_price_per_meter: 98765432
  } as never);
  view("chart");
  await waitFor(() =>
    expect(document.querySelector(".landing-live-price")?.textContent).toBe("۹۸,۷۶۵,۴۳۲ تومان/متر")
  );
  expect(fetchNeighbourhoodMarket).toHaveBeenCalledWith({
    city: "رشت",
    dealTypes: ["SALE"],
    minFiles: 1,
    limit: 100
  });
  expect(screen.getByText(/نه روند زمانی/)).toBeTruthy();
  expect(document.body.textContent).not.toMatch(/۱۳۲٫۸|۴٫۲٪|۱۲ ماه|نمایشی/);
});
it("uses only real valid coordinates and centers a single point", () => {
  expect(projectLocations([row, { ...row, latitude: null }, { ...row, latitude: NaN }])).toEqual([
    { row, x: 50, y: 50 }
  ]);
  expect(projectLocations([])).toEqual([]);
});
it("renders actual neighborhood locations, not fabricated streets", async () => {
  vi.mocked(fetchNeighbourhoodMarket).mockResolvedValue({ items: [row] } as never);
  const { container } = view("map");
  await screen.findByText(/۱ محله با مختصات/);
  expect(container.querySelectorAll("circle")).toHaveLength(1);
  expect(screen.getByText(/نه نقشهٔ خیابان‌ها/)).toBeTruthy();
});
it("shows no radar targets for files without coordinates but preserves returned sample count", async () => {
  vi.mocked(fetchBargains).mockResolvedValue({
    count: 1,
    items: [{ id: "real-id", title: "ملک واقعی", latitude: null, longitude: null }]
  } as never);
  const { container } = view("radar");
  await screen.findByText(/۱ فایل زیر قیمت/);
  expect(container.querySelectorAll(".landing-radar-target")).toHaveLength(0);
  expect(fetchBargains).toHaveBeenCalledWith({ city: "رشت", limit: 30 });
});
it("shows empty data instead of a sample value", async () => {
  vi.mocked(fetchNeighbourhoodMarket).mockResolvedValue({
    items: [],
    median_price_per_meter: null
  } as never);
  view("chart");
  await screen.findByText(/دادهٔ قیمت محله‌ها موجود نیست/);
  expect(document.querySelector(".landing-chart-plot")).toBeNull();
});
it("shows access errors without fallback figures", async () => {
  vi.mocked(fetchBargains).mockRejectedValue(new ApiError(403, "forbidden", "failed"));
  view("radar");
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("دسترسی مجاز"));
  expect(document.querySelector(".landing-radar-disc")).toBeNull();
});

function marketHero() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}
    >
      <HeroMarket />
    </QueryClientProvider>
  );
}
it("renders the floating market card with real medians and neighborhood comparisons only", async () => {
  vi.mocked(fetchNeighbourhoodMarket).mockResolvedValue({
    items: [row, { ...row, neighborhood: "منظریه", median_price_per_meter: 50000000 }],
    median_price_per_meter: 76543210
  } as never);
  const { container } = marketHero();
  await screen.findByText("۷۶,۵۴۳,۲۱۰ تومان/متر");
  expect(container.querySelectorAll("circle")).toHaveLength(2);
  expect(container.querySelector("path[stroke]")?.getAttribute("d")).toContain("L");
  expect(screen.getByText(/نه روند زمانی یا رشد ماهانه/)).toBeTruthy();
  expect(fetchNeighbourhoodMarket).toHaveBeenCalledWith({
    city: "رشت",
    dealTypes: ["SALE"],
    minFiles: 1,
    limit: 100
  });
  expect(container.textContent).not.toMatch(/۲۴۸|الهیه|۲٫۴٪|داده نمایشی/);
});
it("does not invent a time series for a single neighborhood", async () => {
  vi.mocked(fetchNeighbourhoodMarket).mockResolvedValue({
    items: [row],
    median_price_per_meter: row.median_price_per_meter
  } as never);
  const { container } = marketHero();
  await screen.findByText("۹۸,۷۶۵,۴۳۲ تومان/متر");
  expect(container.querySelectorAll("circle")).toHaveLength(1);
  expect(container.querySelector("path")).toBeNull();
});
it("shows an empty market state without fallback values or a chart", async () => {
  vi.mocked(fetchNeighbourhoodMarket).mockResolvedValue({
    items: [],
    median_price_per_meter: null
  } as never);
  const { container } = marketHero();
  await screen.findByText("دادهٔ معتبر قیمت محله‌ها موجود نیست.");
  expect(container.querySelector("svg")).toBeNull();
});
it("preserves nationwide scope and handles access denial without exposing sample prices", async () => {
  state.city = null;
  vi.mocked(fetchNeighbourhoodMarket).mockRejectedValue(new ApiError(403, "forbidden", "failed"));
  const { container } = marketHero();
  await screen.findByText("مشاهدهٔ تحلیل بازار نیازمند ورود و دسترسی مجاز است.");
  expect(fetchNeighbourhoodMarket).toHaveBeenCalledWith({
    city: "تهران",
    dealTypes: ["SALE"],
    minFiles: 1,
    limit: 100
  });
  expect(container.querySelector(".landing-market-price")).toBeNull();
});
