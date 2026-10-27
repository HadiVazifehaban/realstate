import * as React from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CommissionsView, formatCommissionAmount } from "./commissions-view";
import type { CommissionAgreement, CommissionAgreementDetail } from "@/features/network/types";

const state = vi.hoisted(() => ({
  rows: [] as CommissionAgreement[],
  detail: undefined as CommissionAgreementDetail | undefined,
  pending: false,
  error: false,
  tenant: "office-a",
  refetch: vi.fn(),
  lock: vi.fn()
}));
vi.mock("@/hooks/use-auth", () => ({ useAuthContext: () => ({ tenantId: state.tenant }) }));
vi.mock("@/features/network/hooks", () => ({
  useCommissions: () => ({
    data: state.rows,
    isPending: state.pending,
    isError: state.error,
    refetch: state.refetch
  }),
  useCommission: () => ({ data: state.detail, isPending: false, refetch: state.refetch }),
  useLockCommission: () => ({ mutate: state.lock, isPending: false })
}));
vi.mock("next/navigation", () => ({ usePathname: () => "/dashboard/network/commissions" }));

const row = (id: string, currency = "IRR"): CommissionAgreement => ({
  id,
  property_id: null,
  source_agency_id: "office-a",
  target_agency_id: "office-b",
  model: "PERCENTAGE",
  status: "DRAFT",
  basis_amount: 1000,
  currency,
  note: "توافق فروش آپارتمان",
  locked_by: "",
  locked_at: null,
  created_by: "admin",
  created_at: "2026-10-01",
  updated_at: "2026-10-01"
});
const show = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <CommissionsView />
    </QueryClientProvider>
  );
beforeEach(() => {
  state.rows = [row("agreement-one")];
  state.detail = undefined;
  state.pending = false;
  state.error = false;
  state.tenant = "office-a";
  vi.clearAllMocks();
});
afterEach(cleanup);

it("formats stored currency without conversion or a misleading toman label", () => {
  expect(formatCommissionAmount(1000, "IRR")).toBe("۱٬۰۰۰ ریال");
  expect(formatCommissionAmount(0, "IRT")).toBe("۰ تومان");
  expect(formatCommissionAmount(20, "USD")).toBe("۲۰ دلار");
});
it("keeps totals of different currencies separate", () => {
  state.rows.push(row("agreement-two", "USD"));
  show();
  expect(screen.getByText("۱٬۰۰۰ ریال / ۱٬۰۰۰ دلار")).toBeTruthy();
});
it("searches notes and resets empty filters", () => {
  show();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "ویلا" } });
  expect(screen.getByText("توافقی مطابق فیلترها پیدا نشد")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "پاک کردن فیلترها" }));
  expect(screen.getByRole("button", { name: "جزئیات سهم‌ها و پرداخت‌ها" })).toBeTruthy();
});
it("shows empty and error states and retries fetching", () => {
  state.error = true;
  show();
  fireEvent.click(screen.getByRole("button", { name: "تلاش مجدد" }));
  expect(state.refetch).toHaveBeenCalledOnce();
});
it("shows an empty ledger without inventing payments", () => {
  state.rows = [];
  show();
  expect(screen.getByText("توافق کمیسیونی ثبت نشده")).toBeTruthy();
});
it("shows detail amounts and requires confirmation before locking a draft", () => {
  state.detail = {
    ...row("agreement-one"),
    total_paid: 200,
    remaining: 800,
    allocations: [],
    payments: []
  };
  show();
  fireEvent.click(screen.getByRole("button", { name: "جزئیات سهم‌ها و پرداخت‌ها" }));
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText("۸۰۰ ریال")).toBeTruthy();
  fireEvent.click(within(dialog).getByRole("button", { name: "قفل کردن توافق" }));
  expect(state.lock).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "قفل کن" }));
  expect(state.lock).toHaveBeenCalledWith(
    { agreementId: "agreement-one" },
    expect.objectContaining({ onSuccess: expect.any(Function) })
  );
});
it("does not offer locking a settled agreement", () => {
  state.detail = {
    ...row("agreement-one"),
    status: "SETTLED",
    total_paid: 1000,
    remaining: 0,
    allocations: [],
    payments: []
  };
  show();
  fireEvent.click(screen.getByRole("button", { name: "جزئیات سهم‌ها و پرداخت‌ها" }));
  expect(screen.queryByRole("button", { name: "قفل کردن توافق" })).toBeNull();
});
