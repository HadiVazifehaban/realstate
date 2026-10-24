import * as React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/features/landing/components/brand", () => ({
  LandingBrand: ({ dashboard, header }: { dashboard?: boolean; header?: boolean }) => (
    <a href={dashboard ? "/dashboard" : "/"} data-large-brand={header}>
      شکارچی
    </a>
  )
}));
vi.mock("@/features/landing/components/dashboard-top-nav", () => ({
  DashboardTopNav: () => <nav aria-label="ابزارهای سامانه" />
}));
vi.mock("../org-switcher", () => ({ OrgSwitcher: () => <button>Office switcher</button> }));
vi.mock("../themes/theme-selector", () => ({
  ThemeSelector: () => <button>Theme selector</button>
}));
vi.mock("../themes/theme-mode-toggle", () => ({
  ThemeModeToggle: () => <button>Theme mode</button>
}));
vi.mock("./cta-login", () => ({ default: () => <button>Login</button> }));
vi.mock("./user-nav", () => ({ UserNav: () => <button>Profile</button> }));
vi.mock("@/features/notifications/components/notification-center", () => ({
  NotificationCenter: () => <button>Notifications</button>
}));

import Header from "./header";

describe("dashboard header", () => {
  afterEach(cleanup);

  it("renders only the primary RTL row without the contextual search or location controls", () => {
    const { container } = render(<Header />);
    const header = screen.getByRole("banner");
    expect(header.getAttribute("dir")).toBe("rtl");
    expect(header.children).toHaveLength(1);
    expect(container.querySelector(".dashboard-header-context")).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.getByRole("link", { name: "شکارچی" }).getAttribute("data-large-brand")).toBe(
      "true"
    );
  });

  it("keeps navigation, property submission and every utility including the office switcher", () => {
    const { container } = render(<Header />);
    expect(screen.getByRole("navigation", { name: "ابزارهای سامانه" })).not.toBeNull();
    expect(screen.getByRole("link", { name: "ثبت ملک" }).getAttribute("href")).toBe(
      "/dashboard/properties/submit"
    );
    for (const name of ["Office switcher", "Theme mode", "Login", "Profile"]) {
      expect(
        container
          .querySelector(".dashboard-header-utilities")
          ?.contains(screen.getByRole("button", { name }))
      ).toBe(true);
    }
    expect(screen.queryByRole("button", { name: "Notifications" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Theme selector" })).toBeNull();
    expect(container.querySelector("#theme-selector")).toBeNull();
  });
});
