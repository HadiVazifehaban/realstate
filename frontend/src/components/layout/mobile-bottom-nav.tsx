"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icons } from "@/components/icons";
import { useIsMobile } from "@/hooks/use-mobile";

const items = [
  { label: "داشبورد", href: "/dashboard", icon: Icons.home },
  { label: "رادار شکار", href: "/dashboard/properties", icon: Icons.crosshair },
  { label: "شبکه همکاری", href: "/dashboard/network", icon: Icons.building },
  { label: "حساب من", href: "/dashboard/profile", icon: Icons.user }
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
        <span
          aria-hidden="true"
          className={`h-1 w-1 rounded-full bg-[#c5a880] shadow-[0_0_8px_2px_rgba(197,168,128,0.65)] transition-opacity ${active ? "opacity-100" : "opacity-0"}`}
        />
      </Link>
    );
  };

  return (
    <nav
      aria-label="ناوبری موبایل"
      dir="rtl"
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-[#c5a880]/20 bg-[#060b13]/95 px-2 pt-2 pb-[env(safe-area-inset-bottom)] shadow-[0_-12px_36px_rgba(0,0,0,0.28)] backdrop-blur-md md:hidden"
    >
      <div className="mx-auto grid w-full max-w-lg grid-cols-5 items-end gap-1">
        {renderItem(items[0])}
        {renderItem(items[1])}

        <Link
          href="/dashboard/properties/submit"
          aria-label="ثبت ملک"
          title="ثبت ملک"
          className="relative -mt-4 mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-tr from-[#a38255] via-[#c5a880] to-[#e8d5be] text-[#060b13] shadow-lg shadow-[#c5a880]/20 ring-4 ring-[#060b13]/95 transition-transform duration-200 hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#c5a880] focus-visible:ring-offset-2 focus-visible:ring-offset-[#060b13]"
        >
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[#060b13] text-[#c5a880]">
            <Icons.add className="h-6 w-6" />
          </span>
        </Link>

        {renderItem(items[2])}
        {renderItem(items[3])}
      </div>
    </nav>
  );
}
