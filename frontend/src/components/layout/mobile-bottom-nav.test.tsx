import * as React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MobileBottomNav from "./mobile-bottom-nav";

const state = vi.hoisted(() => ({ mobile: true, pathname: "/dashboard/properties" }));

vi.mock("@/hooks/use-mobile", () => ({ useIsMobile: () => state.mobile }));
vi.mock("next/navigation", () => ({ usePathname: () => state.pathname }));

describe("MobileBottomNav", () => {
  beforeEach(() => {
    state.mobile = true;
    state.pathname = "/dashboard/properties";
  });
  afterEach(cleanup);

  it("exposes the property radar in the five-item RTL mobile navigation", () => {
    render(<MobileBottomNav />);
    const radar = screen.getByRole("link", { name: "رادار شکار" });
    expect(radar.getAttribute("href")).toBe("/dashboard/properties");
    expect(radar.getAttribute("aria-current")).toBe("page");
    expect(screen.getAllByRole("link")).toHaveLength(5);
    expect(screen.getByRole("navigation").getAttribute("dir")).toBe("rtl");
  });

  it("keeps the radar active on property details but not on other dashboard pages", () => {
    state.pathname = "/dashboard/properties/123";
    const { rerender } = render(<MobileBottomNav />);
    expect(screen.getByRole("link", { name: "رادار شکار" }).getAttribute("aria-current")).toBe(
      "page"
    );
    state.pathname = "/dashboard/workspaces";
    rerender(<MobileBottomNav />);
    expect(screen.getByRole("link", { name: "رادار شکار" }).getAttribute("aria-current")).toBeNull();
  });

  it("does not change desktop navigation", () => {
    state.mobile = false;
    render(<MobileBottomNav />);
    expect(screen.queryByRole("navigation")).toBeNull();
  });
});
