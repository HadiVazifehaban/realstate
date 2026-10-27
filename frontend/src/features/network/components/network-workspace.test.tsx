import * as React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NetworkPage, NetworkStats } from "./network-page";
import { TransfersView } from "@/app/dashboard/network/transfers/transfers-view";
import { ReferralsView } from "@/app/dashboard/network/referrals/referrals-view";

const state = vi.hoisted(() => ({
  transfers: [] as any[],
  referrals: [] as any[],
  mutate: vi.fn()
}));
vi.mock("next/navigation", () => ({ usePathname: () => "/dashboard/network/referrals" }));
vi.mock("@/components/layout/page-container", () => ({
  default: ({ children }: { children: React.ReactNode }) => <main>{children}</main>
}));
vi.mock("@/hooks/use-auth", () => ({ useAuthContext: () => ({ tenantId: "office-a" }) }));
vi.mock("@/features/network/hooks", () => ({
  useTransfers: () => ({ data: state.transfers }),
  useReferrals: () => ({ data: state.referrals }),
  useUpdateReferralStage: () => ({ mutate: state.mutate, isPending: false })
}));
vi.mock("@/app/dashboard/network/transfers/transfer-create-dialog", () => ({
  TransferCreateDialog: () => <button>ثبت انتقال فایل</button>
}));

beforeEach(() => {
  state.transfers = [];
  state.referrals = [];
});
afterEach(cleanup);
const show = (element: React.ReactNode) =>
  render(<QueryClientProvider client={new QueryClient()}>{element}</QueryClientProvider>);

it("shows six network links with the current page announced", () => {
  render(
    <NetworkPage pageTitle="ارجاع‌ها" pageDescription="پیگیری مشتری">
      <p>محتوا</p>
    </NetworkPage>
  );
  expect(screen.getByRole("navigation").querySelectorAll("a")).toHaveLength(6);
  expect(screen.getByRole("link", { name: /ارجاع‌ها/ }).getAttribute("aria-current")).toBe("page");
  expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("ارجاع‌ها");
});

it("formats actual counts in Persian", () => {
  render(<NetworkStats items={[{ label: "دفاتر", value: 12 }]} />);
  expect(screen.getByText("۱۲")).toBeTruthy();
});

it("keeps create transfer available when there are no transfers", () => {
  show(<TransfersView />);
  expect(screen.getByRole("button", { name: "ثبت انتقال فایل" })).toBeTruthy();
  expect(screen.getByText("هنوز فایلی منتقل نشده")).toBeTruthy();
});

it("filters transfers locally without hiding the create action", () => {
  state.transfers = [
    {
      id: "t1",
      property_id: "property-one",
      status: "COMPLETED",
      from_user: "Ali",
      to_user: "Sara",
      reason: "واگذاری",
      residual_commission_pct: 0
    }
  ];
  show(<TransfersView />);
  fireEvent.change(screen.getByRole("textbox", { name: "جستجوی انتقال‌ها" }), {
    target: { value: "no-match" }
  });
  expect(screen.getByText("انتقالی مطابق فیلترها پیدا نشد")).toBeTruthy();
  expect(screen.getByRole("button", { name: "ثبت انتقال فایل" })).toBeTruthy();
});

it("searches referrals by subject", () => {
  state.referrals = [{ id: "r1", subject: "خرید آپارتمان", stage: "SENT", referral_fee_pct: 5 }];
  show(<ReferralsView />);
  expect(screen.getByText("خرید آپارتمان")).toBeTruthy();
  fireEvent.change(screen.getByRole("textbox", { name: "جستجوی ارجاع‌ها" }), {
    target: { value: "ویلا" }
  });
  expect(screen.queryByText("خرید آپارتمان")).toBeNull();
  expect(screen.getByText("ارجاعی مطابق فیلترها پیدا نشد")).toBeTruthy();
});
