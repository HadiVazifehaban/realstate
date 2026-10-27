import * as React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SharedListingsView } from "./shared-listings-view";
import type { Share } from "@/features/network/types";
import { NetworkApiError } from "@/features/network/api/client";

const state = vi.hoisted(() => ({
  agency: "office-a",
  fetch: vi.fn(),
  extend: vi.fn(),
  params: new URLSearchParams(),
  replace: vi.fn()
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: state.replace }),
  usePathname: () => "/dashboard/network/shared-listings",
  useSearchParams: () => state.params
}));
vi.mock("@/hooks/use-auth", () => ({
  useAuthContext: () => ({ tenantId: state.agency, isLoading: false })
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/features/network/api/client", async (original) => ({
  ...(await original<typeof import("@/features/network/api/client")>()),
  fetchShares: state.fetch,
  extendShare: state.extend
}));

const row = (id: string): Share => ({
  id,
  property_id: id,
  source_agency_id: "office-a",
  target_agency_id: "office-b",
  mode: "SHARE",
  status: "ACTIVE",
  target_agent: "",
  note: "",
  expires_at: null,
  created_by: "broker",
  created_at: "2026-10-01T00:00:00Z",
  revoked_at: null
});
const show = () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  });
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <SharedListingsView />
      </QueryClientProvider>
    )
  };
};
beforeEach(() => {
  state.agency = "office-a";
  state.params = new URLSearchParams();
  state.fetch.mockReset().mockResolvedValue([]);
  state.extend.mockReset();
});
afterEach(cleanup);

it("does not request shares without an office", () => {
  state.agency = "";
  show();
  expect(screen.getByText("دفتر شما شناسایی نشد")).toBeTruthy();
  expect(state.fetch).not.toHaveBeenCalled();
});

it("retries a failed next page at the same offset and refreshes older pages", async () => {
  const first = Array.from({ length: 50 }, (_, index) => row(`file-${index}`));
  let failed = false;
  state.fetch.mockImplementation(async ({ offset }) => {
    if (offset === 50 && !failed) {
      failed = true;
      throw new Error("offline");
    }
    return offset === 50 ? [row("last-file")] : first;
  });
  const { client } = show();
  fireEvent.click(await screen.findByRole("button", { name: /مورد بعدی/ }));
  fireEvent.click(await screen.findByRole("button", { name: "تلاش دوباره" }));
  await screen.findByText(/last-fil/);
  expect(state.fetch.mock.calls.map(([params]) => params.offset)).toEqual([0, 50, 50]);
  first[0] = { ...first[0], note: "updated after mutation" };
  await client.invalidateQueries({ queryKey: ["network", "shares"] });
  expect(await screen.findByText(/updated after mutation/)).toBeTruthy();
});

it("keeps pagination available when local search has no matches", async () => {
  state.fetch.mockResolvedValue(Array.from({ length: 50 }, (_, index) => row(`file-${index}`)));
  show();
  await screen.findByRole("button", { name: /مورد بعدی/ });
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "not-found" } });
  await waitFor(() =>
    expect(screen.getByText("نتیجه‌ای در موارد بارگذاری‌شده پیدا نشد")).toBeTruthy()
  );
  expect(screen.getByRole("button", { name: /مورد بعدی/ })).toBeTruthy();
});

it("does not expose management actions on incoming shares", async () => {
  state.params = new URLSearchParams("direction=incoming");
  state.fetch.mockResolvedValue([row("incoming")]);
  show();
  await screen.findByText(/فایل incoming/);
  expect(screen.queryByRole("button", { name: /تمدید/ })).toBeNull();
});

it("shows a forbidden state instead of an empty successful list", async () => {
  state.fetch.mockRejectedValue(new NetworkApiError(403, "share_forbidden", "not allowed"));
  show();
  expect(await screen.findByText("دسترسی مجاز نیست")).toBeTruthy();
  expect(screen.queryByText("اشتراکی در دسترس نیست")).toBeNull();
});

it("does not keep the previous office's rows after a tenant switch", async () => {
  state.fetch.mockImplementation(async ({ agencyId }) =>
    agencyId === "office-a" ? [row("old-office")] : []
  );
  const { client, rerender } = show();
  await screen.findByText(/فایل old-offi/);
  state.agency = "office-c";
  rerender(
    <QueryClientProvider client={client}>
      <SharedListingsView />
    </QueryClientProvider>
  );
  await screen.findByText("اشتراکی در دسترس نیست");
  expect(screen.queryByText(/فایل old-offi/)).toBeNull();
});

it("blocks repeated extension clicks until the real response arrives", async () => {
  state.fetch.mockResolvedValue([row("extend-me")]);
  let finish!: (share: Share) => void;
  state.extend.mockImplementation(
    () =>
      new Promise<Share>((resolve) => {
        finish = resolve;
      })
  );
  show();
  const button = await screen.findByRole("button", { name: /تمدید/ });
  fireEvent.click(button);
  fireEvent.click(button);
  await waitFor(() => expect(state.extend).toHaveBeenCalledTimes(1));
  finish(row("extend-me"));
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
});
