"use client";

import { ThemeProvider as NextThemesProvider, ThemeProviderProps } from "next-themes";
import { useTheme } from "next-themes";
import { useEffect } from "react";
import { DEFAULT_THEME, normalizeTheme } from "./theme.config";

function ThemePreferenceSync() {
  const { theme, setTheme } = useTheme();
  useEffect(() => {
    if (!theme) return;
    const normalized = normalizeTheme(
      theme,
      window.matchMedia("(prefers-color-scheme: dark)").matches
    );
    if (theme !== normalized) setTheme(normalized);
    document.documentElement.removeAttribute("data-theme");
    document.cookie = `active_theme=${normalized}; path=/; max-age=31536000; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
  }, [theme, setTheme]);
  return null;
}

export default function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      {...props}
      attribute="class"
      defaultTheme={props.defaultTheme ?? DEFAULT_THEME}
      themes={["light", "dark"]}
      enableSystem={false}
    >
      <ThemePreferenceSync />
      {children}
    </NextThemesProvider>
  );
}
