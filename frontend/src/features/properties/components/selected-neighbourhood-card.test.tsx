import * as React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { SelectedNeighbourhoodCard } from "./selected-neighbourhood-card";
import type { NeighbourhoodStat } from "../types";

const row: NeighbourhoodStat = {
  neighborhood: "ولنجک",
  city: "تهران",
  files: 12,
  all_files: 18,
  median_price_per_meter: 200000000,
  median_area: 120,
  median_total_price: null,
  median_deposit: null,
  median_monthly_rent: null,
  bargain_share: 0,
  median_deviation_pct: null,
  latitude: 35.8,
  longitude: 51.4
};

describe("SelectedNeighbourhoodCard", () => {
  beforeEach(() => localStorage.clear());
  afterEach(cleanup);

  it("renders a thin RTL summary without the photo or unavailable metrics in compact mode", () => {
    render(<SelectedNeighbourhoodCard row={row} compact />);
    const card = screen.getByRole("region", { name: "تحلیل محلهٔ ولنجک" });
    expect(card.getAttribute("dir")).toBe("rtl");
    expect(card.className).toContain("py-2.5");
    expect(card.className).not.toContain("lg:min-h-32");
    expect(screen.getByText(/میانهٔ متراژ/)).toBeDefined();
    expect(screen.getByText(/قیمت هر متر:/)).toBeDefined();
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.queryByText("رشد قیمت")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "افزودن به علاقه‌مندی‌ها" }));
    expect(screen.getByRole("button").getAttribute("aria-pressed")).toBe("true");
  });

  it("places the description before metrics and actions in an explicit RTL full-width grid", () => {
    render(<SelectedNeighbourhoodCard row={row} />);
    const card = screen.getByRole("region", { name: "تحلیل محلهٔ ولنجک" });
    expect(card.getAttribute("dir")).toBe("rtl");
    expect(card.className).toContain("w-full");
    expect(card.className).toContain("lg:min-h-32");
    expect(card.className).toContain("lg:grid-cols-2");
    expect(screen.getByTestId("neighbourhood-metrics").className).toContain("grid-cols-2");
    expect(card.children[0]).toBe(screen.getByTestId("neighbourhood-description"));
    expect(card.children[1]).toBe(screen.getByTestId("neighbourhood-metrics"));
    expect(screen.getByText("دادهٔ تاریخی موجود نیست")).toBeDefined();
    expect(screen.getByText("دادهٔ تراکم ساخت موجود نیست")).toBeDefined();
  });

  it("saves favorites per city and neighbourhood and restores them on remount", () => {
    const { unmount } = render(<SelectedNeighbourhoodCard row={row} />);
    fireEvent.click(screen.getByRole("button", { name: "افزودن به علاقه‌مندی‌ها" }));
    expect(screen.getByRole("button").getAttribute("aria-pressed")).toBe("true");
    unmount();
    render(<SelectedNeighbourhoodCard row={row} />);
    fireEvent.click(screen.getByRole("button", { name: "حذف از علاقه‌مندی‌ها" }));
    expect(screen.getByRole("button").getAttribute("aria-pressed")).toBe("false");
  });

  it("uses real listing media and falls back safely when it cannot load", () => {
    render(<SelectedNeighbourhoodCard row={row} photo="/properties/media/file/123" />);
    const photo = screen.getByRole("img");
    expect(photo.getAttribute("src")).toBe("/backend/api/v1/properties/media/file/123");
    fireEvent.error(photo);
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.getByLabelText("تصویر محله موجود نیست")).toBeDefined();
  });
});
