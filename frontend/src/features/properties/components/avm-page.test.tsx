import * as React from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const fixture = vi.hoisted(() => ({
  items: [
    {
      neighborhood: "ولنجک",
      city: "تهران",
      files: 12,
      all_files: 15,
      median_price_per_meter: 200000000,
      median_area: 120,
      bargain_share: 0.2,
      latitude: 35.8,
      longitude: 51.4
    },
    {
      neighborhood: "یوسف‌آباد",
      city: "تهران",
      files: 8,
      all_files: 10,
      median_price_per_meter: 100000000,
      median_area: 85,
      bargain_share: 0,
      latitude: 35.7,
      longitude: 51.4
    }
  ]
}));
vi.mock("../hooks", () => ({
  useGisAreas: () => ({ data: { cities: ["تهران"] } }),
  useNeighbourhoodMarket: () => ({
    data: { items: fixture.items, count: 2, total_files: 25, priced_files: 20 },
    isPending: false,
    isError: false
  }),
  useNeighbourhoodProperties: () => ({ data: { items: [] }, isPending: false, isError: false })
}));
vi.mock("@/store/useCityStore", () => ({ useActiveCityName: () => "تهران" }));
vi.mock("./market-map", () => ({
  MarketMap: ({ bubbles }: { bubbles: { id: string }[] }) => (
    <div data-testid="map-bubbles">{bubbles.map((b) => b.id).join(",")}</div>
  )
}));
vi.mock("./property-avm-sheet", () => ({ PropertyAvmSheet: () => <button>ارزش‌گذاری ملک</button> }));
vi.mock("./listing-card", () => ({ ListingCard: () => null }));
vi.mock("@/components/layout/page-container", () => ({
  default: ({ children }: React.PropsWithChildren) => <main>{children}</main>
}));
import AvmPage from "./avm-page";

describe("AVM three-column workspace", () => {
  afterEach(cleanup);

  it("groups neighborhoods and listings on the right, controls/specs in the middle, and map separately", () => {
    render(<AvmPage />);
    const right = screen.getByRole("complementary", { name: "محله‌ها و فایل‌های مرتبط" });
    const center = screen.getByRole("complementary", { name: "کنترل‌ها و مشخصات محله" });
    expect(within(right).getByRole("complementary", { name: "رتبه‌بندی محله‌ها" })).toBeDefined();
    expect(within(right).getByRole("region", { name: "املاک محلهٔ انتخاب‌شده" })).toBeDefined();
    expect(within(center).getByRole("region", { name: "فیلترهای تحلیل بازار" })).toBeDefined();
    const unified = within(center).getByRole("region", { name: "مشخصات محله و راهنمای نقشه" });
    expect(within(unified).getByText(/میانهٔ متراژ/)).toBeDefined();
    expect(within(unified).getByRole("region", { name: "راهنمای رنگ نقشه بازار" })).toBeDefined();
    expect(screen.getByRole("region", { name: "نقشهٔ بازار" }).id).toBe("market-map");
    expect(screen.getByRole("region", { name: "نقشه و رتبه‌بندی محله‌ها" }).getAttribute("dir")).toBe(
      "rtl"
    );
    expect(unified.textContent).not.toContain("تومان/متر تومان");
  });

  it("filters neighborhood metrics and map bubbles together, then restores them on reset", () => {
    render(<AvmPage />);
    fireEvent.change(screen.getByRole("spinbutton", { name: "حداقل مقدار شاخص محله" }), {
      target: { value: "150000000" }
    });
    expect(screen.getByTestId("map-bubbles").textContent).toBe("ولنجک");
    const ranking = screen.getByRole("complementary", { name: "رتبه‌بندی محله‌ها" });
    expect(within(ranking).queryByText("یوسف‌آباد")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "پاک‌کردن محدوده" }));
    expect(screen.getByTestId("map-bubbles").textContent).toContain("یوسف‌آباد");
  });

  it("keeps recovery controls available when the range has no matching neighborhoods", () => {
    render(<AvmPage />);
    fireEvent.change(screen.getByRole("spinbutton", { name: "حداقل مقدار شاخص محله" }), {
      target: { value: "300000000" }
    });
    fireEvent.change(screen.getByRole("spinbutton", { name: "حداکثر مقدار شاخص محله" }), {
      target: { value: "100000000" }
    });
    expect(screen.getByRole("alert").textContent).toContain("حداقل نباید");
    expect(screen.getByRole("button", { name: "پاک‌کردن محدوده" })).toBeDefined();
    expect(screen.getByTestId("map-bubbles").textContent).toBe("");
  });
});
