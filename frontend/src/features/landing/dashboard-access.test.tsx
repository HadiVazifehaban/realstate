import * as React from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { accountNavItems, navGroups } from "@/config/nav-config";
import type { NavItem } from "@/types";

const state = vi.hoisted(() => ({
  roles: [] as string[],
  tenantId: null as string | null,
  signOut: vi.fn(),
  pathname: "/dashboard"
}));
vi.mock("next/navigation", () => ({ usePathname: () => state.pathname }));
vi.mock("@/lib/utils", () => ({ AUTH_BYPASS_ENABLED: false, KEYCLOAK_ENABLED: true }));
vi.mock("@/hooks/use-auth", () => ({
  useAuthContext: () => state,
  useAuthOrganization: () => state.tenantId,
  useAuthSignOut: () => state.signOut
}));
import { DashboardAccess, AccessTree } from "./components/dashboard-access";
import { DashboardTopNav } from "./components/dashboard-top-nav";
import { useFilteredNavGroups } from "@/hooks/use-nav";

const flatten = (items: NavItem[]): NavItem[] =>
  items.flatMap((item) => [item, ...flatten(item.items ?? [])]);
function Comparison() {
  const groups = useFilteredNavGroups(navGroups);
  return (
    <>
      <nav aria-label="sidebar-source">
        <AccessTree items={groups.flatMap((g) => g.items)} />
      </nav>
      <DashboardAccess />
      <DashboardTopNav />
    </>
  );
}

describe("dashboard landing navigation parity", () => {
  afterEach(() => {
    cleanup();
    state.roles = [];
    state.tenantId = null;
    state.pathname = "/dashboard";
  });

  it("inventories all four groups, current parents and nested items before filtering", () => {
    expect(navGroups).toHaveLength(4);
    const parents = navGroups.flatMap((g) => g.items);
    expect(parents).toHaveLength(15);
    expect(flatten(parents)).toHaveLength(32);
    expect(accountNavItems).toHaveLength(3);
  });

  for (const roles of [[], ["ROLE_JUNIOR_BROKER"], ["ROLE_ADMIN"], ["ROLE_DATA_ANALYST"]]) {
    it(`matches every sidebar-filtered route and title for ${roles.join() || "no roles"}`, () => {
      state.roles = roles;
      state.tenantId = roles.length ? "tenant" : null;
      render(<Comparison />);
      const expected = within(
        screen.getByRole("navigation", { name: "sidebar-source" })
      ).getAllByRole("link");
      const actual = [...document.querySelectorAll(".landing-access-group a")];
      const top = [...document.querySelectorAll(".landing-top-panel a")];
      expect(top.map((a) => [a.textContent, a.getAttribute("href")])).toEqual(
        expected.map((a) => [a.textContent, a.getAttribute("href")])
      );
      expect(actual.find((a) => a.textContent === "خانهٔ شکارچی")?.getAttribute("href")).toBe(
        "/dashboard"
      );
      expect(actual.map((a) => [a.textContent, a.getAttribute("href")])).toEqual(
        expected.map((a) => [a.textContent, a.getAttribute("href")])
      );
      expect(
        screen
          .getAllByText("دستیار هوشمند شکارچی")
          .every((el) => el.closest('[aria-disabled="true"]'))
      ).toBe(true);
      expect(actual.some((a) => a.getAttribute("href") === "/dashboard/ai-chat")).toBe(false);
      const account = screen.getByRole("navigation", { name: "حساب و خدمات کاربری" });
      expect(!!within(account).queryByRole("link", { name: "امور مالی" })).toBe(!!state.tenantId);
      expect(!!actual.find((a) => a.getAttribute("href") === "/dashboard/pii")).toBe(
        roles.includes("ROLE_ADMIN") || roles.includes("ROLE_DATA_ANALYST")
      );
    });
  }
  it("highlights the exact active route and its group without activating the home group", () => {
    state.pathname = "/dashboard/network/commissions";
    state.roles = ["ROLE_ADMIN"];
    render(<DashboardTopNav />);
    expect(document.querySelectorAll('.landing-top-group[data-active="true"]')).toHaveLength(1);
    expect(
      document.querySelector('.landing-top-group[data-active="true"] summary')?.textContent
    ).toContain("معاملات و شبکه");
    expect(document.querySelector('a[aria-current="page"]')?.getAttribute("href")).toBe(
      state.pathname
    );
    expect(document.querySelectorAll("summary > svg")).toHaveLength(8);
  });

  it("closes the top navigation on Escape and returns focus to its summary", () => {
    render(<DashboardTopNav />);
    const details = document.querySelector(".landing-top-group") as HTMLDetailsElement;
    details.open = true;
    fireEvent.keyDown(document, { key: "Escape" });
    expect(details.open).toBe(false);
    expect(document.activeElement).toBe(details.querySelector("summary"));
  });

  it("closes on an outside pointer press and after selecting an existing link", () => {
    render(<DashboardTopNav />);
    const details = document.querySelector(".landing-top-group") as HTMLDetailsElement;
    details.open = true;
    fireEvent.pointerDown(document.body);
    expect(details.open).toBe(false);
    details.open = true;
    const link = details.querySelector("a")!;
    link.addEventListener("click", (event) => event.preventDefault());
    fireEvent.click(link);
    expect(details.open).toBe(false);
  });

  it("keeps the live badge text and icon on its existing route", () => {
    const { container } = render(
      <AccessTree
        items={[{ title: "رادار", url: "/dashboard/properties", icon: "dashboard", badge: "زنده" }]}
      />
    );
    expect(container.querySelector(".dashboard-live-badge")?.textContent).toBe("زنده");
    expect(screen.getByRole("link").getAttribute("href")).toBe("/dashboard/properties");
    expect(container.querySelector("a > svg")).not.toBeNull();
  });
});
