import * as React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FooterSocialLinks } from "./footer-social-links";
import { SocialLinksAdmin } from "./social-links-admin";
import { safeSocialUrl, type SocialLink } from "./api";

const state = vi.hoisted(() => ({
  roles: ["ROLE_ADMIN"],
  publicLinks: vi.fn(),
  adminLinks: vi.fn(),
  save: vi.fn(),
  toggle: vi.fn(),
  remove: vi.fn(),
  reorder: vi.fn(),
  success: vi.fn(),
  error: vi.fn()
}));
vi.mock("@/hooks/use-auth", () => ({
  useAuthContext: () => ({ roles: state.roles, isLoading: false })
}));
vi.mock("sonner", () => ({ toast: { success: state.success, error: state.error } }));
vi.mock("./api", async (original) => ({
  ...(await original<typeof import("./api")>()),
  fetchPublicSocialLinks: state.publicLinks,
  fetchAdminSocialLinks: state.adminLinks,
  saveSocialLink: state.save,
  toggleSocialLink: state.toggle,
  deleteSocialLink: state.remove,
  reorderSocialLinks: state.reorder
}));
const link = (id = "a", name = "تلگرام"): SocialLink => ({
  id,
  display_name: name,
  platform_key: "telegram",
  icon_name: "telegram",
  url: `https://t.me/${id}`,
  is_active: true,
  sort_order: id === "a" ? 0 : 1
});
const show = (element: React.ReactNode) =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false, retryDelay: 0 } } })}
    >
      {element}
    </QueryClientProvider>
  );

beforeEach(() => {
  state.roles = ["ROLE_ADMIN"];
  state.publicLinks.mockReset().mockResolvedValue([]);
  state.adminLinks.mockReset().mockResolvedValue([link(), link("b", "ایتا")]);
  state.save.mockReset().mockResolvedValue(link());
  state.toggle.mockReset().mockResolvedValue(link());
  state.remove.mockReset().mockResolvedValue(undefined);
  state.reorder.mockReset().mockResolvedValue([]);
});
afterEach(cleanup);

describe("dynamic footer links", () => {
  it("renders only active safe database links in order with accessible local icons", async () => {
    state.publicLinks.mockResolvedValue([
      link("b", "ایتا"),
      link(),
      { ...link("c"), is_active: false },
      { ...link("d"), url: "javascript:alert(1)" }
    ]);
    show(<FooterSocialLinks />);
    await screen.findByRole("navigation");
    const links = screen.getAllByRole("link");
    expect(links.map((item) => item.getAttribute("aria-label"))).toEqual(["تلگرام", "ایتا"]);
    expect(links[0].getAttribute("rel")).toBe("noopener noreferrer");
    expect(links[0].querySelector("svg")?.classList.contains("w-5")).toBe(true);
  });
  it("does not invent links for empty or unavailable configuration", async () => {
    state.publicLinks.mockRejectedValue(new Error("offline"));
    show(<FooterSocialLinks />);
    await waitFor(() => expect(state.publicLinks).toHaveBeenCalled());
    expect(screen.queryByRole("link")).toBeNull();
  });
  it.each([
    "javascript:alert(1)",
    "//evil.example",
    "https://user:pass@example.com",
    "data:text/html,test"
  ])("rejects unsafe destination %s", (url) => expect(safeSocialUrl(url)).toBe(false));
});

describe("social management", () => {
  it("never fetches or displays management controls for non-admins", () => {
    state.roles = ["ROLE_SUPERVISOR"];
    show(<SocialLinksAdmin />);
    expect(screen.getByRole("alert")).toBeDefined();
    expect(state.adminLinks).not.toHaveBeenCalled();
    expect(screen.queryByRole("form")).toBeNull();
  });
  it("creates and edits with success feedback", async () => {
    show(<SocialLinksAdmin />);
    await screen.findByRole("button", { name: "ویرایش تلگرام" });
    fireEvent.change(screen.getByLabelText("نشانی مقصد"), {
      target: { value: "https://t.me/real" }
    });
    fireEvent.click(screen.getByRole("button", { name: "افزودن پیوند" }));
    await waitFor(() =>
      expect(state.save).toHaveBeenCalledWith(
        expect.objectContaining({ url: "https://t.me/real", sort_order: 2 }),
        undefined
      )
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "ویرایش تلگرام" }).hasAttribute("disabled")).toBe(
        false
      )
    );
    fireEvent.click(screen.getByRole("button", { name: "ویرایش تلگرام" }));
    fireEvent.change(screen.getByLabelText("نام نمایشی"), { target: { value: "نام جدید" } });
    fireEvent.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));
    await waitFor(() =>
      expect(state.save).toHaveBeenLastCalledWith(
        expect.objectContaining({ display_name: "نام جدید" }),
        "a"
      )
    );
    expect(state.success).toHaveBeenCalled();
  });
  it("optimistically toggles visibility and rolls back on failure", async () => {
    let reject!: (reason: Error) => void;
    state.toggle.mockImplementation(
      () =>
        new Promise((_, fail) => {
          reject = fail;
        })
    );
    show(<SocialLinksAdmin />);
    fireEvent.click(await screen.findByRole("switch", { name: "نمایش تلگرام" }));
    await waitFor(() =>
      expect(
        screen.getByRole("switch", { name: "نمایش تلگرام" }).getAttribute("aria-checked")
      ).toBe("false")
    );
    reject(new Error("ذخیره نشد"));
    await screen.findByText("ذخیره نشد");
    await waitFor(() =>
      expect(
        screen.getByRole("switch", { name: "نمایش تلگرام" }).getAttribute("aria-checked")
      ).toBe("true")
    );
    expect(state.error).toHaveBeenCalled();
  });
  it("persists ordering and deletes only after confirmation", async () => {
    show(<SocialLinksAdmin />);
    fireEvent.click(await screen.findByRole("button", { name: "انتقال ایتا به بالا" }));
    await waitFor(() => expect(state.reorder).toHaveBeenCalledWith(["b", "a"]));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "حذف تلگرام" }).hasAttribute("disabled")).toBe(
        false
      )
    );
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    fireEvent.click(screen.getByRole("button", { name: "حذف تلگرام" }));
    expect(state.remove).not.toHaveBeenCalled();
    confirm.mockReturnValue(true);
    fireEvent.click(screen.getByRole("button", { name: "حذف تلگرام" }));
    await waitFor(() => expect(state.remove).toHaveBeenCalledWith("a"));
  });
});
