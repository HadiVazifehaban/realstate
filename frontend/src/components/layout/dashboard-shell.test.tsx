import * as React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
const state = vi.hoisted(() => ({ pathname: "/dashboard" }));
vi.mock("next/navigation", () => ({ usePathname: () => state.pathname }));
vi.mock("./app-sidebar", () => ({ default: () => <aside>sidebar</aside> }));
vi.mock("./header", () => ({ default: () => <header>dashboard header</header> }));
vi.mock("./mobile-bottom-nav", () => ({ default: () => <nav>mobile bottom</nav> }));
vi.mock("./info-sidebar", () => ({ InfoSidebar: () => <aside>info</aside> }));
vi.mock("@/components/ui/infobar", () => ({
  InfobarProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));
vi.mock("@/components/ui/sidebar", () => ({
  SidebarInset: ({ children }: { children: React.ReactNode }) => <main>{children}</main>
}));
import { DashboardShell } from "./dashboard-shell";
describe("dashboard horizontal shell", () => {
  afterEach(cleanup);
  it("gives home a full-width main and shared top header without side or bottom navigation", () => {
    state.pathname = "/dashboard";
    render(<DashboardShell>landing</DashboardShell>);
    expect(screen.getByRole("main").textContent).toContain("landing");
    expect(screen.getByRole("main").id).toBe("main-content");
    expect(screen.queryByText("sidebar")).toBeNull();
    expect(screen.getByText("dashboard header")).not.toBeNull();
    expect(screen.queryByText("mobile bottom")).toBeNull();
  });
  it("keeps one shared header without a sidebar across tool and home routes", () => {
    state.pathname = "/dashboard/avm";
    const { rerender } = render(<DashboardShell>tool</DashboardShell>);
    expect(screen.queryByText("sidebar")).toBeNull();
    expect(screen.getByText("dashboard header")).not.toBeNull();
    state.pathname = "/dashboard/";
    rerender(<DashboardShell>landing</DashboardShell>);
    expect(screen.queryByText("sidebar")).toBeNull();
    expect(screen.getByText("landing")).not.toBeNull();
    expect(screen.getAllByRole("banner")).toHaveLength(1);
    expect(screen.queryByText("mobile bottom")).toBeNull();
  });
});
