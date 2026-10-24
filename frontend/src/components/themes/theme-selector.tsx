"use client";

import { useThemeConfig } from "@/components/themes/active-theme";
import { useEffect, useState } from "react";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";

import { Icons } from "../icons";
import { THEMES } from "./theme.config";

export function ThemeSelector({ compact = false }: { compact?: boolean }) {
  const { activeTheme, setActiveTheme } = useThemeConfig();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <div className="flex items-center gap-2">
      <Label htmlFor="theme-selector" className="sr-only">
        Theme
      </Label>
      <Select
        items={THEMES.map((theme) => ({ value: theme.value, label: theme.name }))}
        value={mounted ? activeTheme : null}
        onValueChange={(value) => {
          if (value !== null) setActiveTheme(value);
        }}
      >
        <SelectTrigger
          id="theme-selector"
          aria-label={compact ? "انتخاب پوسته" : undefined}
          className={
            compact
              ? "size-8 justify-center p-0 [&>[data-slot=select-icon]]:hidden"
              : "justify-start *:data-[slot=select-value]:w-24 [&>[data-slot=select-icon]]:hidden"
          }
        >
          <span className={compact ? "text-[#e5a87b]" : "text-muted-foreground hidden sm:block"}>
            <Icons.palette />
          </span>
          {!compact && (
            <>
              <span className="text-muted-foreground block sm:hidden">Theme</span>
              <SelectValue placeholder="Select a theme" />
            </>
          )}
        </SelectTrigger>
        <SelectContent align="end">
          {THEMES.length > 0 && (
            <>
              <SelectGroup>
                <SelectLabel>حالت نمایش</SelectLabel>
                {THEMES.map((theme) => (
                  <SelectItem key={theme.name} value={theme.value}>
                    {theme.name}
                  </SelectItem>
                ))}
              </SelectGroup>
            </>
          )}
        </SelectContent>
      </Select>
    </div>
  );
}
