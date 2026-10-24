"use client";
import { ReactNode } from "react";
import { useTheme } from "next-themes";
import { DEFAULT_THEME } from "./theme.config";
// Compatibility adapter; next-themes is the sole source of theme state.
export function ActiveThemeProvider({ children }: { children: ReactNode; initialTheme?: string }) {
  return children;
}
export function useThemeConfig() {
  const { resolvedTheme, setTheme } = useTheme();
  return { activeTheme: resolvedTheme ?? DEFAULT_THEME, setActiveTheme: setTheme };
}
