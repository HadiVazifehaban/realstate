import { afterEach, expect, it, vi } from "vitest";
import { fetchCooperations, fetchShares, fetchNetworkOverview, fetchNetworkReports } from "./client";

vi.mock("@/lib/auth/session", () => ({
  authHeaders: async () => ({ Authorization: "Bearer test" })
}));
vi.mock("@/lib/api-base-url", () => ({
  apiBaseUrl: () => "https://api.example",
  networkFailureMessage: () => "offline"
}));
afterEach(() => vi.unstubAllGlobals());

it("serializes the share agency and pagination using the server contract", async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetch);
  await fetchShares({
    agencyId: "office-a",
    direction: "incoming",
    status: "ACTIVE",
    limit: 50,
    offset: 100
  });
  const url = new URL(fetch.mock.calls[0][0]);
  expect(Object.fromEntries(url.searchParams)).toEqual({
    agency_id: "office-a",
    direction: "incoming",
    status: "ACTIVE",
    limit: "50",
    offset: "100"
  });
  expect(url.searchParams.has("agencyId")).toBe(false);
});

it("preserves cooperation request pagination", async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetch);
  await fetchCooperations({ agency_id: "office-a", limit: 50, offset: 50 });
  expect(new URL(fetch.mock.calls[0][0]).searchParams.get("offset")).toBe("50");
});

it.each([fetchNetworkOverview, fetchNetworkReports])('uses the canonical report scope parameter', async (load) => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
  vi.stubGlobal('fetch', fetch);
  await load({ agencyId: 'office-a' });
  expect(Object.fromEntries(new URL(fetch.mock.calls[0][0]).searchParams)).toEqual({ agency_id: 'office-a' });
  expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer test');
});

it.each([fetchNetworkOverview, fetchNetworkReports])('omits undefined scope without serializing null', async (load) => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
  vi.stubGlobal('fetch', fetch);
  await load();
  expect(new URL(fetch.mock.calls[0][0]).search).toBe('');
});
