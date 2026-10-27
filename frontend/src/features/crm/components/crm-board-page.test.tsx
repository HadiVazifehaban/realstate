import * as React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import CrmBoardPage from "./crm-board-page";
import { BoardStatsStrip } from "./board-stats-strip";
import { EMPTY_FILTERS, matchesFilters } from "./board-toolbar";

const state = vi.hoisted(() => ({
  data: {
    items: [
      {
        id: "lead-1",
        title: "آپارتمان شیراز",
        neighborhood: "معالی‌آباد",
        city: "شیراز",
        source: "INTERNAL_AGENCY",
        is_bargain: false,
        stage: "NEW_FILE",
        updated_at: "2026-10-25T10:00:00Z",
        total_price: 1000000
      }
    ]
  },
  pending: false,
  error: false,
  fetching: false,
  statsPending: false,
  statsError: false
}));

vi.mock("@/components/layout/page-container", () => ({
  default: ({ children }: { children: React.ReactNode }) => <main>{children}</main>
}));
vi.mock("@/hooks/use-auth", () => ({
  useAuthContext: () => ({ roles: ["ROLE_AGENCY_MANAGER"], saasTier: "PRO" })
}));
vi.mock("../hooks", () => ({
  useLeads: () => ({
    data: state.data,
    isPending: state.pending,
    isError: state.error,
    isFetching: state.fetching,
    dataUpdatedAt: Date.UTC(2026, 9, 25, 10, 30)
  }),
  useBoardStats: () => ({
    isPending: state.statsPending,
    isError: state.statsError,
    data: {
      columns: [],
      total: 12,
      open_value: 1000000,
      closed_value: 2000000,
      conversion_pct: 50,
      bargains: 2,
      lost: 1
    }
  })
}));
vi.mock("./lead-board", () => ({
  LeadBoard: ({
    filters,
    onOpenLead
  }: {
    filters: typeof EMPTY_FILTERS;
    onOpenLead: (id: string) => void;
  }) => (
    <div data-testid="lead-board">
      {matchesFilters(
        {
          title: "آپارتمان شیراز",
          neighborhood: "معالی‌آباد",
          city: "شیراز",
          source: "INTERNAL_AGENCY",
          is_bargain: false
        },
        filters
      ) ? (
        <button onClick={() => onOpenLead("lead-1")}>آپارتمان شیراز</button>
      ) : (
        <p>نتیجه‌ای نیست</p>
      )}
    </div>
  )
}));
vi.mock("../api/client", () => ({ fetchLead: vi.fn(async () => ({ timeline: [] })) }));
vi.mock("./lead-detail-drawer", () => ({
  LeadDetailDrawer: ({ leadId }: { leadId: string | null }) =>
    leadId ? <p>جزئیات {leadId}</p> : null
}));
vi.mock("./lost-leads-drawer", () => ({
  LostLeadsDrawer: () => <button>بایگانی پرونده‌ها</button>
}));
vi.mock("./new-lead-dialog", () => ({ NewLeadDialog: () => <button>افزودن لید</button> }));

beforeEach(() => {
  Object.assign(state, {
    pending: false,
    error: false,
    fetching: false,
    statsPending: false,
    statsError: false
  });
});
afterEach(cleanup);

it("keeps the desk actions, RTL workspace, view switch and financial disclaimer", () => {
  const { container } = render(<CrmBoardPage />);
  expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("میز کار معاملات");
  expect(container.querySelector(".crm-workspace")?.getAttribute("dir")).toBe("rtl");
  expect(screen.getByRole("button", { name: "افزودن لید" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "بایگانی پرونده‌ها" })).toBeTruthy();
  expect(screen.getByRole("tab", { name: "کانبان" })).toBeTruthy();
  expect(screen.getByRole("tab", { name: "جدول" })).toBeTruthy();
  expect(screen.getByText(/نه درآمد دفتر یا ارزش قطعی معامله/)).toBeTruthy();
  expect(screen.getByText(/آخرین دریافت:/)).toBeTruthy();
});

it("filters the board, clears filters and opens existing lead details", () => {
  render(<CrmBoardPage />);
  fireEvent.change(screen.getByRole("textbox", { name: "جست‌وجو در تخته" }), {
    target: { value: "اصفهان" }
  });
  expect(screen.getByText("نتیجه‌ای نیست")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "پاک کردن فیلتر" }));
  fireEvent.click(screen.getByRole("button", { name: "آپارتمان شیراز" }));
  expect(screen.getByText("جزئیات lead-1")).toBeTruthy();
});

it("toggles bargains without changing the overall statistics", () => {
  render(<CrmBoardPage />);
  const button = screen.getByRole("button", { name: "فقط شکارها" });
  fireEvent.click(button);
  expect(button.getAttribute("aria-pressed")).toBe("true");
  expect(screen.getByText("نتیجه‌ای نیست")).toBeTruthy();
  expect(screen.getByText("۱۲")).toBeTruthy();
});

it("switches to the filtered table empty state and back to the board", async () => {
  render(<CrmBoardPage />);
  fireEvent.change(screen.getByRole("textbox", { name: "جست‌وجو در تخته" }), {
    target: { value: "اصفهان" }
  });
  fireEvent.click(screen.getByRole("tab", { name: "جدول" }));
  await waitFor(() =>
    expect(screen.getByRole("tab", { name: "جدول" }).getAttribute("aria-selected")).toBe("true")
  );
  expect(screen.getByText("پرونده‌ای با این فیلترها پیدا نشد.")).toBeTruthy();
  fireEvent.click(screen.getByRole("tab", { name: "کانبان" }));
  expect(screen.getByTestId("lead-board")).toBeTruthy();
});

it.each([
  ["pending", "در حال دریافت داده‌ها…"],
  ["error", "دریافت داده‌ها ناموفق بود"],
  ["fetching", "در حال به‌روزرسانی…"]
] as const)("reports the real %s query state", (key, message) => {
  state[key] = true;
  render(<CrmBoardPage />);
  expect(screen.getByText(message)).toBeTruthy();
  expect(screen.queryByText(/آخرین دریافت:/)).toBeNull();
});

it("renders a named loading state and a non-blocking statistics error", () => {
  state.statsPending = true;
  const { rerender } = render(<BoardStatsStrip />);
  expect(screen.getByRole("status", { name: "در حال دریافت آمار میز کار" })).toBeTruthy();
  state.statsPending = false;
  state.statsError = true;
  rerender(<BoardStatsStrip />);
  expect(screen.getByText(/آمار تخته در دسترس نیست/)).toBeTruthy();
});
