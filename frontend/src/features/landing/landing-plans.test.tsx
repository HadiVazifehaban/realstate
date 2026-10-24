import * as React from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
const state = vi.hoisted(() => ({
  isPending: false,
  isError: false,
  data: { plans: [] as unknown[] },
  refetch: vi.fn()
}));
vi.mock("@tanstack/react-query", () => ({ useQuery: () => state }));
import { LandingPlans } from "./components/landing-plans";

describe("API-backed landing pricing", () => {
  afterEach(() => {
    cleanup();
    state.isPending = false;
    state.isError = false;
    state.data.plans = [];
    state.refetch.mockClear();
  });
  it("displays API values and only navigates to billing without creating orders", () => {
    state.data.plans = [
      {
        id: "monthly",
        title: "برنز ماهانه",
        price_toman: 499000,
        duration_days: 30,
        listing_quota: 50,
        sms_quota: 30,
        advisor_quota: 3,
        regions_quota: 1,
        is_unlimited: false,
        features: []
      }
    ];
    render(<LandingPlans />);
    expect(screen.getByText(/۴۹۹٬۰۰۰/)).toBeDefined();
    expect(
      screen.getByRole("link", { name: "مشاهده و انتخاب برنز ماهانه" }).getAttribute("href")
    ).toBe("/dashboard/billing");
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByText(/منطقهٔ تهران|تخفیف/)).toBeNull();
  });
  it("uses an honest loading state without fallback prices", () => {
    state.isPending = true;
    render(<LandingPlans />);
    expect(screen.getByRole("status")).toBeDefined();
    expect(screen.queryByRole("article")).toBeNull();
  });
  it("renders reference tiers with actual quotas/features and no invented discounts", () => {
    state.data.plans = [
      {
        id: "free",
        title: "پایه رایگان",
        price_toman: 0,
        duration_days: 30,
        listing_quota: 3,
        sms_quota: 0,
        regions_quota: 0,
        advisor_quota: 1,
        is_unlimited: false,
        features: ["AVM پایه"]
      },
      {
        id: "monthly",
        title: "برنز ماهانه",
        price_toman: 610000,
        duration_days: 30,
        listing_quota: 50,
        sms_quota: 30,
        regions_quota: 1,
        advisor_quota: 3,
        is_unlimited: false,
        features: []
      },
      {
        id: "quarterly",
        title: "نقره‌ای فصلی",
        price_toman: 1500000,
        duration_days: 90,
        listing_quota: 150,
        sms_quota: 100,
        regions_quota: 2,
        advisor_quota: 8,
        is_unlimited: false,
        features: []
      },
      {
        id: "yearly",
        title: "طلایی سالانه",
        price_toman: 5700000,
        duration_days: 365,
        listing_quota: null,
        sms_quota: 500,
        regions_quota: 1000,
        advisor_quota: null,
        is_unlimited: true,
        features: ["PDF تحلیلی AVM", "مدیر حساب اختصاصی"]
      }
    ];
    const { container } = render(<LandingPlans />);
    expect(screen.getAllByRole("article")).toHaveLength(4);
    ["FREE", "BRONZE", "SILVER", "GOLD"].forEach((label) =>
      expect(screen.getByText(label)).toBeDefined()
    );
    const bronze = within(screen.getByRole("article", { name: "برنز ماهانه" }));
    expect(bronze.getByText(/۶۱۰٬۰۰۰/)).toBeDefined();
    expect(bronze.getByText("سهمیهٔ مناطق رادار: ۱")).toBeDefined();
    const gold = within(screen.getByRole("article", { name: "طلایی سالانه" }));
    expect(gold.getByText(/۵٬۷۰۰٬۰۰۰/)).toBeDefined();
    expect(gold.getByText("PDF تحلیلی AVM")).toBeDefined();
    expect(gold.getByText("سهمیهٔ مناطق رادار: ۱٬۰۰۰")).toBeDefined();
    expect(screen.queryByText(/تخفیف|برای همیشه|۵ استعلام|۲۲ منطقه|پیشنهاد ویژه/)).toBeNull();
    expect(container.querySelectorAll(".landing-plan-check svg").length).toBeGreaterThan(16);
    expect(
      screen
        .getAllByRole("link")
        .every((link) => link.getAttribute("href") === "/dashboard/billing")
    ).toBe(true);
  });
  it("does not invent the four reference plans if the API catalog is empty", () => {
    render(<LandingPlans />);
    expect(screen.queryByRole("article")).toBeNull();
    expect(screen.getByText("در حال حاضر پلنی برای نمایش ارائه نشده است.")).toBeDefined();
  });
  it("offers retry on error and never fabricates plan data", () => {
    state.isError = true;
    render(<LandingPlans />);
    expect(screen.getByRole("alert").textContent).toContain("قیمت تأییدنشده");
    fireEvent.click(screen.getByRole("button", { name: "تلاش دوباره" }));
    expect(state.refetch).toHaveBeenCalledOnce();
    expect(screen.queryByRole("article")).toBeNull();
  });
});
