import * as React from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const renderPage = () =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <LandingPage />
    </QueryClientProvider>
  );

vi.mock("next/image", () => ({
  default: ({
    fill: _fill,
    priority: _priority,
    unoptimized: _unoptimized,
    ...props
  }: React.ImgHTMLAttributes<HTMLImageElement> & {
    fill?: boolean;
    priority?: boolean;
    unoptimized?: boolean;
  }) => <img {...props} />
}));

import { LandingPage } from "./components/landing-page";
import { landingRoutes, publicNavigation } from "./config";
import { LandingBrand } from "./components/brand";

vi.mock("@/features/billing/api/client", () => ({
  fetchPlans: async () => ({ plans: [] }),
  toman: (n: number) => String(n)
}));
vi.mock("@/features/properties/api/client", () => ({
  ApiError: class extends Error {},
  fetchProperties: async () => ({ items: [], count: 0, limit: 6, offset: 0 }),
  fetchNeighbourhoodMarket: async () => ({ items: [], count: 0, median_price_per_meter: null }),
  fetchBargains: async () => ({ items: [], count: 0 }),
  fetchGisAreas: async () => ({ provinces: [], cities: [] })
}));

describe("public landing", () => {
  afterEach(cleanup);

  it("keeps the skyline visible in light mode without changing dark-mode opacity", () => {
    const css = readFileSync(resolve(process.cwd(), "src/features/landing/landing.css"), "utf8");
    const lightImage = css.match(/html:not\(\.dark\) \.landing-hero-image\s*\{([^}]+)\}/)?.[1];
    const opacity = Number(lightImage?.match(/opacity:\s*([\d.]+)/)?.[1]);
    expect(opacity).toBeGreaterThanOrEqual(0.6);
    expect(opacity).toBeLessThanOrEqual(1);
    expect(css).toMatch(/\.landing-hero-image\s*\{[^}]*opacity:\s*0\.9\s*;/);
  });

  it("preserves the original logo asset at 134px in the dashboard frame", () => {
    const { container } = render(<LandingBrand dashboard header />);
    const image = container.querySelector("img");
    expect(image?.getAttribute("src")).toMatch(/^\/brand\/logo-dark\.png\?v=/);
    expect(image?.getAttribute("width")).toBe("134");
    expect(image?.getAttribute("height")).toBe("134");
    expect(container.querySelector(".dashboard-brand-mark")).not.toBeNull();
    expect(screen.getByRole("link").getAttribute("href")).toBe("/dashboard");
    expect(screen.queryByText("شکارچی")).toBeNull();
    expect(screen.queryByText("SHEKARCHI")).toBeNull();
  });

  it("renders one Persian heading, the actual hero asset, and real tool links", () => {
    renderPage();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.queryByText("AVM · بازار املاک ایران")).toBeNull();
    expect(screen.getByRole("img", { name: /چشم‌انداز شب تهران/ }).getAttribute("src")).toBe(
      "/images/tehran-night-skyline.webp"
    );
    expect(screen.getAllByRole("article")).toHaveLength(3);
    for (const link of screen.getAllByRole("link")) {
      expect(link.getAttribute("href")).not.toBe("#");
      expect(link.getAttribute("href")).not.toMatch(/^javascript:/);
    }
    const navigation = screen.getByRole("navigation", { name: "ناوبری اصلی" });
    for (const item of publicNavigation) {
      expect(within(navigation).getByRole("link", { name: item.label }).getAttribute("href")).toBe(
        item.href
      );
    }
    expect(screen.queryByText(/ثبت آگهی رایگان|دادهٔ لحظه‌ای|تضمین سرمایه‌گذاری/)).toBeNull();
  });

  it("renders detailed reference previews in chart/map/radar order with genuine links", () => {
    const { container } = renderPage();
    const cards = Array.from(container.querySelectorAll(".landing-tool-card"));
    expect(cards.map((card) => card.querySelector(".landing-preview")?.className)).toEqual([
      "landing-preview landing-preview-chart",
      "landing-preview landing-preview-map",
      "landing-preview landing-preview-radar"
    ]);
    expect(cards.map((card) => card.querySelector("a")?.getAttribute("href"))).toEqual([
      landingRoutes.avm,
      landingRoutes.map,
      landingRoutes.radar
    ]);
    expect(container.querySelectorAll(".landing-tool-detail li")).toHaveLength(9);
    for (const card of cards) {
      expect(card.querySelector(".landing-preview")?.getAttribute("aria-label")).toBeTruthy();
      expect(card.querySelector(".landing-preview")?.textContent).not.toMatch(
        /نمایشی|۱۳۲٫۸|۴٫۲٪|۱۲ ماه/
      );
    }
    const ids = Array.from(container.querySelectorAll(".landing-preview [id]")).map((el) => el.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("opens an accessible auth chooser linking to the existing flows and restores focus", async () => {
    renderPage();
    const trigger = screen.getByRole("button", { name: "ورود / ثبت‌نام" });
    trigger.focus();
    fireEvent.click(trigger);
    const dialog = await screen.findByRole("dialog", { name: "به شکارچی خوش آمدید" });
    expect(dialog.getAttribute("dir")).toBe("rtl");
    expect(
      within(dialog)
        .getByRole("link", { name: /ورود به حساب/ })
        .getAttribute("href")
    ).toBe(landingRoutes.signIn);
    expect(
      within(dialog).getByRole("link", { name: "ایجاد حساب کاربری" }).getAttribute("href")
    ).toBe(landingRoutes.signUp);
    expect(within(dialog).queryByRole("textbox")).toBeNull();
    fireEvent.keyDown(dialog, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(trigger));
  });

  it("closes the auth chooser with its Persian close button", async () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "ورود / ثبت‌نام" }));
    fireEvent.click(await screen.findByRole("button", { name: "بستن پنجرهٔ ورود" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("opens the RTL mobile navigation and closes it after choosing a real route", async () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "بازکردن منوی اصلی" }));
    const dialog = await screen.findByRole("dialog", { name: "کاوش در شکارچی" });
    const link = within(dialog).getByRole("link", { name: "ابزارهای هوشمند" });
    expect(link.getAttribute("href")).toBe("#professional-tools");
    // Prevent jsdom navigation; still exercise the component's close handler.
    link.addEventListener("click", (e) => e.preventDefault());
    fireEvent.click(link);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("uses the shared full-width header frame and original logo", () => {
    const { container } = renderPage();
    const header = container.querySelector("header.dashboard-top-header");
    expect(header).not.toBeNull();
    expect(header?.querySelector(".dashboard-header-primary")).not.toBeNull();
    expect(header?.querySelector(".dashboard-brand-mark img")?.getAttribute("width")).toBe("134");
    expect(header?.querySelector(".landing-brand")?.getAttribute("href")).toBe("/");
    expect(container.querySelector(".landing-header-inner")).toBeNull();
    for (const item of publicNavigation) {
      if (item.href.startsWith("#")) {
        expect(container.querySelector(item.href)).not.toBeNull();
      }
    }
  });

  it("updates the shared header scroll state", () => {
    const { container } = renderPage();
    Object.defineProperty(window, "scrollY", { value: 50, configurable: true });
    fireEvent.scroll(window);
    expect(container.querySelector("header")?.classList.contains("is-scrolled")).toBe(true);
    Object.defineProperty(window, "scrollY", { value: 0, configurable: true });
  });

  it("references the existing route files and optimized supplied image", () => {
    for (const route of Object.values(landingRoutes)) {
      const pathname = route.split("#")[0];
      const path = resolve(process.cwd(), "src/app", pathname.slice(1));
      const catchAll = pathname === landingRoutes.signIn ? "[[...sign-in]]" : "[[...sign-up]]";
      expect(
        existsSync(resolve(path, "page.tsx")) || existsSync(resolve(path, catchAll, "page.tsx"))
      ).toBe(true);
    }
    expect(existsSync(resolve(process.cwd(), "public/images/tehran-night-skyline.webp"))).toBe(
      true
    );
    expect(existsSync(resolve(process.cwd(), "public/images/tehran-night-skyline.jpg"))).toBe(true);
    expect(
      readFileSync(
        resolve(process.cwd(), "src/features/properties/components/avm-page.tsx"),
        "utf8"
      )
    ).toContain('id="market-map"');
  });
  it("renders the reference-style atmospheric layers and four-column footer with real destinations", () => {
    const { container } = renderPage();
    expect(container.querySelector(".landing-hero-grid")).not.toBeNull();
    expect(container.querySelector(".landing-grain")?.getAttribute("aria-hidden")).toBe("true");
    expect(container.querySelectorAll("canvas.landing-particles")).toHaveLength(1);
    const footer = screen.getByRole("contentinfo");
    expect(within(footer).getByText("شکارچی")).not.toBeNull();
    expect(within(footer).getByText("SHEKARCHI")).not.toBeNull();
    const developer = within(footer).getByRole("link", { name: "چشم‌انداز اوج فردا (AVG Tech)" });
    expect(developer.getAttribute("href")).toBe("https://ojfarda.ir");
    expect(developer.getAttribute("target")).toBe("_blank");
    expect(developer.getAttribute("rel")).toBe("noopener noreferrer");
    expect(container.querySelector(".landing-footer-top")?.children).toHaveLength(4);
    expect(within(footer).getByRole("heading", { name: "دسترسی سریع" })).not.toBeNull();
    expect(container.querySelector(".landing-hero-image")?.getAttribute("src")).toContain(
      "tehran-night-skyline.webp"
    );
    expect(within(footer).getByRole("heading", { name: "خدمات شکارچی" })).not.toBeNull();
    for (const link of within(footer).getAllByRole("link", { name: /ورود به سامانه/ })) {
      expect(link.getAttribute("href")).toBe("/dashboard");
    }
    expect(footer.textContent).not.toContain("پرداخت امن");
  });
});
