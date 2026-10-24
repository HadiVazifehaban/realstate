import * as React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  mobile: true,
  roles: ["ROLE_ADMIN"],
  signOut: vi.fn(),
  push: vi.fn(),
  organization: null as string | null
}));

vi.mock("@/hooks/use-mobile", () => ({ useIsMobile: () => state.mobile }));
vi.mock("@/hooks/use-auth", () => ({
  useAuthContext: () => ({
    user: { fullName: "کاربر", emailAddresses: [{ emailAddress: "user@example.test" }] },
    saasTier: "طلایی",
    roles: state.roles
  }),
  useAuthSignOut: () => state.signOut,
  useAuthOrganization: () => state.organization
}));
vi.mock("@/components/navigation/MobileProfileSheet", () => ({
  MobileProfileSheet: () => <div data-testid="mobile-profile-sheet">پروفایل موبایل</div>
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: state.push }) }));

import { UserNav } from "./user-nav";
import { SidebarProvider } from "@/components/ui/sidebar";
import { useNotificationStore } from "@/features/notifications/utils/store";

describe("UserNav responsive profile menu", () => {
  afterEach(cleanup);

  beforeEach(() => {
    state.mobile = true;
    state.roles = ["ROLE_ADMIN"];
    state.signOut.mockReset();
    state.push.mockReset();
    state.organization = null;
  });

  it("renders the bottom sheet below the mobile breakpoint", () => {
    render(<UserNav />);
    expect(screen.getByTestId("mobile-profile-sheet")).not.toBeNull();
    expect(screen.queryByRole("button", { name: "بازکردن منوی حساب کاربری" })).toBeNull();
  });

  it("does not duplicate the desktop profile in the header", () => {
    state.mobile = false;
    const { container } = render(<UserNav mobileOnly />);
    expect(container.innerHTML).toBe("");
  });

  it.each([false, true])(
    "renders a sidebar-native trigger and account actions (expanded: %s)",
    async (expanded) => {
      state.mobile = false;
      state.organization = "tenant";
      render(
        <SidebarProvider defaultOpen={expanded}>
          <UserNav placement="sidebar" />
        </SidebarProvider>
      );
      const trigger = screen.getByRole("button", { name: "بازکردن منوی حساب کاربری" });
      expect(trigger.getAttribute("data-sidebar")).toBe("menu-button");
      expect(trigger.textContent).toContain("کاربر");
      expect(trigger.textContent).toContain("مدیر سامانه");
      expect(trigger.querySelector('[data-slot="avatar"]')).not.toBeNull();
      trigger.focus();
      fireEvent.keyDown(trigger, { key: "ArrowDown" });
      const menu = await screen.findByRole("menu");
      expect(menu.className).toContain("bg-sidebar");
      expect(screen.getByRole("menuitem", { name: "امور مالی" })).toBeDefined();
      expect(screen.getByRole("menuitem", { name: /اعلان‌ها/ }).textContent).toContain(
        new Intl.NumberFormat("fa-IR").format(useNotificationStore.getState().unreadCount())
      );
      fireEvent.click(screen.getByRole("menuitem", { name: "حساب کاربری" }));
      expect(state.push).toHaveBeenCalledWith("/dashboard/profile");
      await waitFor(() => expect(trigger.getAttribute("aria-expanded")).toBe("false"));
    }
  );

  it("preserves organization gating and notification/logout routes in the sidebar", async () => {
    state.mobile = false;
    render(
      <SidebarProvider>
        <UserNav placement="sidebar" />
      </SidebarProvider>
    );
    const trigger = screen.getByRole("button", { name: "بازکردن منوی حساب کاربری" });
    fireEvent.click(trigger);
    expect(screen.queryByRole("menuitem", { name: "امور مالی" })).toBeNull();
    fireEvent.click(await screen.findByRole("menuitem", { name: /اعلان‌ها/ }));
    expect(state.push).toHaveBeenCalledWith("/dashboard/notifications");
    fireEvent.click(trigger);
    fireEvent.click(await screen.findByRole("menuitem", { name: "خروج" }));
    await waitFor(() =>
      expect(state.signOut).toHaveBeenCalledWith({ redirectUrl: "/auth/sign-in" })
    );
  });

  it("renders the real user chip and an RTL glass dropdown at desktop width", async () => {
    state.mobile = false;
    render(<UserNav />);
    expect(screen.queryByTestId("mobile-profile-sheet")).toBeNull();
    expect(screen.getByText("مدیر سامانه")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "بازکردن منوی حساب کاربری" }));
    const menu = await screen.findByRole("menu");
    expect(menu.getAttribute("dir")).toBe("rtl");
    expect(menu.className).toContain("backdrop-blur-xl");
    expect(screen.getByText("user@example.test")).toBeDefined();
    fireEvent.click(screen.getByRole("menuitem", { name: /امنیت و سطوح دسترسی/ }));
    expect(state.push).toHaveBeenCalledWith("/dashboard/roles");
  });

  it.each([
    ["اعلان‌ها", "/dashboard/notifications"],
    ["رادار شکار قیمت", "/dashboard/properties"],
    ["تنظیمات حساب کاربری", "/dashboard/profile"],
    ["امنیت و سطوح دسترسی (RBAC)", "/dashboard/roles"],
    ["اشتراک و صورتحساب‌ها", "/dashboard/billing"],
    ["کمیسیون و تسویه", "/dashboard/network/commissions"]
  ])("navigates to %s and closes the menu", async (label, destination) => {
    state.mobile = false;
    render(<UserNav />);
    const trigger = screen.getByRole("button", { name: "بازکردن منوی حساب کاربری" });
    fireEvent.click(trigger);
    const item = await screen.findByRole("menuitem", {
      name: label === "اعلان‌ها" ? /اعلان‌ها/ : label
    });
    const icon = item.querySelector("svg");
    expect(icon).not.toBeNull();
    expect(icon?.getAttribute("aria-hidden")).toBe("true");
    expect(icon?.classList.contains("size-4")).toBe(true);
    if (label === "اعلان‌ها") {
      expect(item.querySelector("svg")).not.toBeNull();
      expect(item.textContent).toContain(
        new Intl.NumberFormat("fa-IR").format(useNotificationStore.getState().unreadCount())
      );
    }
    fireEvent.click(item);
    expect(state.push).toHaveBeenCalledWith(destination);
    await waitFor(() => expect(trigger.getAttribute("aria-expanded")).toBe("false"));
  });

  it("logs out via the auth provider without clearing unrelated browser data", async () => {
    state.mobile = false;
    localStorage.setItem("profile-test-preference", "preserved");
    render(<UserNav />);
    fireEvent.click(screen.getByRole("button", { name: "بازکردن منوی حساب کاربری" }));
    const logout = await screen.findByRole("menuitem", { name: /خروج امن از حساب/ });
    expect(logout.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
    fireEvent.click(logout);
    await waitFor(() =>
      expect(state.signOut).toHaveBeenCalledWith({ redirectUrl: "/auth/sign-in" })
    );
    expect(localStorage.getItem("profile-test-preference")).toBe("preserved");
    localStorage.removeItem("profile-test-preference");
  });

  it("does not invent a role when no realm role is available", () => {
    state.mobile = false;
    state.roles = [];
    render(<UserNav />);
    expect(screen.getByText("حساب کاربری")).toBeDefined();
    expect(screen.queryByText("مدیر سامانه")).toBeNull();
  });

  it("closes with Escape and updates the trigger expanded state", async () => {
    state.mobile = false;
    render(<UserNav />);
    const trigger = screen.getByRole("button", { name: "بازکردن منوی حساب کاربری" });
    fireEvent.click(trigger);
    const menu = await screen.findByRole("menu");
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    fireEvent.keyDown(menu, { key: "Escape" });
    await waitFor(() => expect(trigger.getAttribute("aria-expanded")).toBe("false"));
  });

  it("shows a retryable error when provider sign-out fails", async () => {
    state.mobile = false;
    state.signOut.mockRejectedValue(new Error("unavailable"));
    render(<UserNav />);
    fireEvent.click(screen.getByRole("button", { name: "بازکردن منوی حساب کاربری" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: /خروج امن از حساب/ }));
    expect(await screen.findByRole("alert")).toBeDefined();
    await waitFor(() =>
      expect(
        screen.getByRole("menuitem", { name: /خروج امن از حساب/ }).getAttribute("aria-disabled")
      ).not.toBe("true")
    );
  });
});
