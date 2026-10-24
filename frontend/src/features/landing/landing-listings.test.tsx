import * as React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
const state = vi.hoisted(() => ({ fetch: vi.fn() }));
vi.mock("@/features/properties/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/features/properties/api/client")>();
  return { ...original, fetchProperties: state.fetch };
});
vi.mock("@/features/properties/components/listing-card", () => ({
  ListingCard: ({ property }: { property: { id: string; title: string } }) => (
    <article>
      <a href={`/dashboard/properties/${property.id}`}>{property.title}</a>
    </article>
  )
}));
import { LandingListings } from "./components/landing-listings";
import { ApiError } from "@/features/properties/api/client";
const renderListings = () =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <LandingListings />
    </QueryClientProvider>
  );
describe("landing inventory showcase", () => {
  afterEach(() => {
    cleanup();
    state.fetch.mockReset();
  });
  it("renders real API listings and applies submitted filters without filtering a local sample", async () => {
    state.fetch.mockResolvedValue({ items: [{ id: "real-id", title: "ملک واقعی" }], count: 12 });
    renderListings();
    expect((await screen.findByRole("link", { name: "ملک واقعی" })).getAttribute("href")).toBe(
      "/dashboard/properties/real-id"
    );
    fireEvent.change(screen.getByLabelText("شهر"), { target: { value: "شیراز" } });
    fireEvent.change(screen.getByLabelText("حداقل متراژ"), { target: { value: "120" } });
    fireEvent.change(screen.getByLabelText("حداکثر قیمت یا رهن"), {
      target: { value: "3000000000" }
    });
    fireEvent.click(screen.getByRole("button", { name: "جستجو" }));
    await waitFor(() =>
      expect(state.fetch).toHaveBeenLastCalledWith(
        expect.objectContaining({ city: "شیراز", min_area: 120, max_price: 3000000000, limit: 6 })
      )
    );
    fireEvent.click(screen.getByRole("button", { name: "رهن و اجاره" }));
    await waitFor(() =>
      expect(state.fetch).toHaveBeenLastCalledWith(
        expect.objectContaining({ deal_type: ["RENT", "FULL_MORTGAGE"] })
      )
    );
    fireEvent.click(screen.getByRole("button", { name: "فرصت‌های زیر قیمت بازار" }));
    await waitFor(() =>
      expect(state.fetch).toHaveBeenLastCalledWith(
        expect.objectContaining({ valuation_status: "BARGAIN" })
      )
    );
    fireEvent.click(screen.getByRole("button", { name: "فایل‌های دفاتر" }));
    await waitFor(() =>
      expect(state.fetch).toHaveBeenLastCalledWith(
        expect.objectContaining({ submitter_type: "AGENCY", valuation_status: undefined })
      )
    );
    fireEvent.click(screen.getByRole("button", { name: "پاک‌کردن فیلترها" }));
    expect((screen.getByLabelText("شهر") as HTMLInputElement).value).toBe("");
    expect(screen.getByRole("button", { name: "همه", pressed: true })).not.toBeNull();
    expect(screen.getByRole("button", { name: "تازه‌ترین آگهی‌ها", pressed: true })).not.toBeNull();
  });
  it("shows an honest empty state", async () => {
    state.fetch.mockResolvedValue({ items: [], count: 0 });
    renderListings();
    expect(await screen.findByText("آگهی منطبق پیدا نشد")).not.toBeNull();
    expect(screen.queryByRole("article")).toBeNull();
  });
  it("preserves access protection instead of rendering fake listings", async () => {
    state.fetch.mockRejectedValue(new ApiError(401, "unauthorized", "Unauthorized"));
    renderListings();
    expect(await screen.findByRole("alert")).not.toBeNull();
    expect(screen.getByRole("link", { name: "ورود به حساب" }).getAttribute("href")).toContain(
      "callbackUrl=%2Fdashboard%23search"
    );
  });
  it("supports retry after a failed request", async () => {
    state.fetch
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValue({ items: [], count: 0 });
    renderListings();
    fireEvent.click(await screen.findByRole("button", { name: "تلاش دوباره" }));
    expect(await screen.findByText("آگهی منطبق پیدا نشد")).not.toBeNull();
  });
});
