export const DEFAULT_THEME = "dark";
export const THEMES = [
  { name: "تاریک — شکارچی", value: "dark" },
  { name: "روشن — Cloud", value: "light" }
];
export function normalizeTheme(value: string | undefined, systemDark = true) {
  if (value === "light" || value === "dark") return value;
  if (value === "system") return systemDark ? "dark" : "light";
  return DEFAULT_THEME;
}
