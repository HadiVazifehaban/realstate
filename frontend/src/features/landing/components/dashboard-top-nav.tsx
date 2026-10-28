"use client";

import { useEffect, useRef } from "react";
import { useFilteredNavGroups } from "@/hooks/use-nav";
import { navGroups } from "@/config/nav-config";
import { AccessTree } from "./dashboard-access";
import { usePathname } from "next/navigation";
import { Icons } from "@/components/icons";
import type { NavItem } from "@/types";

const containsPath = (items: NavItem[], path: string): boolean =>
  items.some(
    (item) => !item.disabled && (item.url === path || containsPath(item.items ?? [], path))
  );

export function DashboardTopNav({ ariaLabel = "ابزارهای سامانه" }: { ariaLabel?: string }) {
  const groups = useFilteredNavGroups(navGroups);
  const pathname = usePathname()?.replace(/\/$/, "") ?? "";
  const root = useRef<HTMLElement>(null);
  useEffect(() => {
    const close = () =>
      root.current?.querySelectorAll("details[open]").forEach((el) => el.removeAttribute("open"));
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) close();
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        const active = root.current?.querySelector("details[open] > summary") as HTMLElement | null;
        close();
        active?.focus();
      }
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, []);
  return (
    <nav ref={root} className="landing-dashboard-nav" aria-label={ariaLabel}>
      {groups.map((group) => {
        const Icon = Icons[group.items[0]?.icon ?? "dashboard"];
        return (
          <details
            key={group.label}
            className="landing-top-group"
            data-active={containsPath(group.items, pathname) || undefined}
            onToggle={(event) => {
              if (event.currentTarget.open)
                root.current?.querySelectorAll("details[open]").forEach((el) => {
                  if (el !== event.currentTarget) el.removeAttribute("open");
                });
            }}
          >
            <summary>
              <Icon size={18} aria-hidden />
              {group.label}
              <Icons.chevronDown size={14} className="dashboard-nav-chevron" aria-hidden />
            </summary>
            <div
              className="landing-top-panel"
              onClick={(event) => {
                if ((event.target as HTMLElement).closest("a"))
                  root.current
                    ?.querySelectorAll("details[open]")
                    .forEach((el) => el.removeAttribute("open"));
              }}
            >
              <AccessTree items={group.items} activePath={pathname} />
            </div>
          </details>
        );
      })}
    </nav>
  );
}
