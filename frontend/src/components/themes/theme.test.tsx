import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useTheme } from "next-themes";
import ThemeProvider from "./theme-provider";
import { DEFAULT_THEME, THEMES, normalizeTheme } from "./theme.config";
import { useThemeConfig } from "./active-theme";

function Probe() {
  const { themes } = useTheme();
  const { activeTheme, setActiveTheme } = useThemeConfig();
  return (
    <>
      <output>{activeTheme}</output>
      <span data-testid="options">{themes.join(",")}</span>
      <button onClick={() => setActiveTheme(activeTheme === "dark" ? "light" : "dark")}>
        change
      </button>
    </>
  );
}

describe("two-mode theme", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => ({
        matches: false,
        addListener: vi.fn(),
        removeListener: vi.fn()
      }))
    );
  });
  afterEach(() => {
    cleanup();
    localStorage.removeItem("theme");
    document.documentElement.className = "";
    vi.unstubAllGlobals();
  });
  it("offers only Cloud light and Shekarchi dark, with a dark default", () => {
    expect(THEMES.map((t) => t.value)).toEqual(["dark", "light"]);
    expect(DEFAULT_THEME).toBe("dark");
    expect(normalizeTheme("vercel")).toBe("dark");
    expect(normalizeTheme("system", false)).toBe("light");
    expect(normalizeTheme("system", true)).toBe("dark");
    expect(normalizeTheme("light")).toBe("light");
  });
  it("switches through one state, persists the choice and restores it after remount", async () => {
    localStorage.removeItem("theme");
    const view = render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>
    );
    expect(screen.getByTestId("options").textContent).toBe("light,dark");
    await waitFor(() => expect(document.documentElement.classList.contains("dark")).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: "change" }));
    await waitFor(() => expect(document.documentElement.classList.contains("light")).toBe(true));
    expect(localStorage.getItem("theme")).toBe("light");
    expect(document.cookie).toContain("active_theme=light");
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
    view.unmount();
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>
    );
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe("light"));
  });
});
