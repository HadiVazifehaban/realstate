"use client";

import Link from "next/link";
import { Icons } from "@/components/icons";
import { accountNavItems, navGroups } from "@/config/nav-config";
import { useFilteredNavGroups } from "@/hooks/use-nav";
import { useAuthOrganization, useAuthSignOut } from "@/hooks/use-auth";
import type { NavItem } from "@/types";

/** Keep every node, including parents with their own route and disabled previews. */
export function AccessTree({ items, activePath }: { items: NavItem[]; activePath?: string }) {
  return (
    <ul className="landing-access-tree">
      {items.map((item) => {
        const Icon = Icons[item.icon ?? "dashboard"];
        const content = (
          <>
            <Icon size={18} aria-hidden />
            <span>{item.title}</span>
            {item.badge && (
              <small className={item.badge === "زنده" ? "dashboard-live-badge" : undefined}>
                {item.badge}
              </small>
            )}
          </>
        );
        return (
          <li key={`${item.url}:${item.title}`}>
            {item.disabled ? (
              <span className="landing-access-disabled" aria-disabled="true">
                {content}
              </span>
            ) : (
              <Link href={item.url} aria-current={activePath === item.url ? "page" : undefined}>
                {content}
              </Link>
            )}
            {item.items?.length ? <AccessTree items={item.items} activePath={activePath} /> : null}
          </li>
        );
      })}
    </ul>
  );
}

export function DashboardAccess() {
  const groups = useFilteredNavGroups(navGroups);
  const organization = useAuthOrganization();
  const signOut = useAuthSignOut();
  return (
    <section
      id="dashboard-access"
      className="landing-container landing-access"
      aria-labelledby="access-heading"
    >
      <div className="landing-section-heading">
        <p className="landing-kicker">تمام ابزارهای حساب شما، در یک نگاه</p>
        <h2 id="access-heading">دسترسی سریع به بخش‌های شکارچی</h2>
        <p>تمام ابزارها با همان ترتیب و سطح دسترسی، از منوی بالای صفحه نیز در دسترس‌اند.</p>
      </div>
      <div className="landing-access-grid">
        {groups.map((group) => (
          <details open key={group.label} className="landing-access-group">
            <summary>{group.label}</summary>
            <AccessTree items={group.items} />
          </details>
        ))}
      </div>
      <nav className="landing-account-links" aria-label="حساب و خدمات کاربری">
        {accountNavItems
          .filter((item) => !item.access?.requireOrg || organization)
          .map((item) => (
            <Link key={item.url} href={item.url}>
              {item.title}
            </Link>
          ))}
        <button type="button" onClick={() => void signOut({ redirectUrl: "/auth/sign-in" })}>
          خروج از حساب
        </button>
      </nav>
    </section>
  );
}
