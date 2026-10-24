import * as React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import HeaderLocationPicker from "./header-location-picker";

const state = vi.hoisted(() => ({
  pending: false,
  error: false,
  refetch: vi.fn(),
  setParams: vi.fn(),
  setActiveCity: vi.fn()
}));

// Cities outside the small offline/popular-city list must remain selectable.
const provinces = [
  { name: "آذربایجان شرقی", cities: ["تبریز", "مراغه"] },
  { name: "سیستان و بلوچستان", cities: ["زاهدان", "چابهار"] },
  ...Array.from({ length: 29 }, (_, i) => ({ name: `استان ${i}`, cities: [`شهر ${i}`] }))
];

vi.mock("@/features/properties/hooks", () => ({
  useGisAreas: () => ({
    data: state.pending || state.error ? undefined : { provinces },
    isPending: state.pending,
    isError: state.error,
    isFetching: state.pending,
    refetch: state.refetch
  }),
  useInventoryCities: () => ({ data: { cities: ["تبریز"] } })
}));
vi.mock("@/store/useCityStore", () => ({
  useActiveCityName: () => "تبریز",
  useCityStore: (selector: (store: { setActiveCity: typeof state.setActiveCity }) => unknown) =>
    selector({ setActiveCity: state.setActiveCity })
}));
vi.mock("nuqs", async (importOriginal) => ({
  ...(await importOriginal<typeof import("nuqs")>()),
  useQueryStates: () => [{ city: [] }, state.setParams]
}));

describe("HeaderLocationPicker API options", () => {
  beforeEach(() => {
    state.pending = false;
    state.error = false;
    vi.clearAllMocks();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true }))
    );
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders all 31 API provinces and selects a non-popular city", () => {
    render(<HeaderLocationPicker />);
    fireEvent.click(screen.getByRole("button", { name: "انتخاب شهر و استان" }));
    provinces.forEach(({ name }) => expect(screen.getByText(name)).toBeDefined());
    fireEvent.click(screen.getByRole("button", { name: /سیستان و بلوچستان.*شهر/ }));
    fireEvent.click(screen.getByRole("button", { name: "چابهار" }));
    expect(state.setParams).toHaveBeenCalledWith({ city: ["چابهار"] });
  });

  it("searches cities from the API, not just inventory cities", () => {
    render(<HeaderLocationPicker />);
    fireEvent.click(screen.getByRole("button", { name: "انتخاب شهر و استان" }));
    fireEvent.change(screen.getByPlaceholderText("جستجوی شهر یا استان..."), {
      target: { value: "مراغه" }
    });
    expect(screen.getByRole("button", { name: /مراغه/ })).toBeDefined();
  });

  it("shows loading and offers retry instead of silently presenting an incomplete list", () => {
    state.pending = true;
    const { rerender } = render(<HeaderLocationPicker />);
    fireEvent.click(screen.getByRole("button", { name: "انتخاب شهر و استان" }));
    expect(screen.getByText("در حال دریافت استان‌ها و شهرها…")).toBeDefined();
    state.pending = false;
    state.error = true;
    rerender(<HeaderLocationPicker />);
    expect(screen.getByText(/فهرست کامل استان‌ها و شهرها دریافت نشد/)).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "تلاش دوباره" }));
    expect(state.refetch).toHaveBeenCalledOnce();
  });
});
