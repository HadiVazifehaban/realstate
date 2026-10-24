"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icons } from "@/components/icons";
import { useIsMobile } from "@/hooks/use-mobile";

const items = [
  { label: "رادار املاک", href: "/dashboard/properties", icon: Icons.crosshair },
  { label: "فایلینگ", href: "/dashboard/workspaces", icon: Icons.page },
  { label: "پنل کاربری", href: "/dashboard/users", icon: Icons.user },
  { label: "اعلان‌ها", href: "/dashboard/notifications", icon: Icons.notification }
] as const;

function isActivePath(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function MobileBottomNav() {
  const isMobile = useIsMobile();
  const pathname = usePathname();

  if (!isMobile) return null;

  const renderItem = (item: (typeof items)[number]) => {
    const Icon = item.icon;
    const active = isActivePath(pathname, item.href);

    return (
      <Link
        key={item.href}
        href={item.href}
        aria-current={active ? "page" : undefined}
        className={`group flex min-w-0 flex-col items-center justify-center gap-1 rounded-xl px-1 py-1 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-ffd8be)]/70 ${
          active ? "text-primary" : "text-[var(--brand-c88252)]/75 hover:text-primary"
        }`}
      >
        <Icon className="h-5 w-5 shrink-0 transition-transform duration-200 group-hover:-translate-y-0.5" />
        <span className="max-w-full truncate text-[9px] font-medium leading-4 min-[380px]:text-[10px]">
          {item.label}
        </span>
      </Link>
    );
  };

  return (
    <nav
      aria-label="ناوبری موبایل"
      dir="rtl"
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-[var(--brand-c88252)]/30 bg-background/90 px-2 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] shadow-[0_-12px_36px_rgba(0,0,0,0.28)] backdrop-blur-md md:hidden"
    >
      <div className="mx-auto grid w-full max-w-lg grid-cols-5 items-end gap-1">
        {renderItem(items[0])}
        {renderItem(items[1])}

        <Link
          href="/dashboard/overview"
          aria-label="داشبورد — صفحه اصلی"
          title="داشبورد"
          aria-current={isActivePath(pathname, "/dashboard/overview") ? "page" : undefined}
          className="relative -mt-7 mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-r from-[var(--brand-c88252)] to-[var(--brand-ffd8be)] text-primary-foreground shadow-lg shadow-[var(--brand-c88252)]/20 ring-4 ring-[var(--brand-060b13)]/90 transition-transform duration-200 hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-ffd8be)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--brand-060b13)]"
        >
          <Icons.dashboard className="h-6 w-6" />
        </Link>

        {renderItem(items[2])}
        {renderItem(items[3])}
      </div>
    </nav>
  );
}
