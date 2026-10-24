"use client";

import * as React from "react";
import Link from "next/link";
import { Icons, type Icon } from "@/components/icons";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerSwipeHandle,
  DrawerTitle,
  DrawerTrigger
} from "@/components/ui/drawer";
import type { Subscription } from "@/features/billing/api/client";
import { useCurrentSubscription } from "@/hooks/use-current-subscription";
import type { SessionUser } from "@/hooks/use-auth";
import { formatPersianDigits, formatPersianNumber } from "@/lib/formatters";
import { KEYCLOAK_ENABLED } from "@/lib/utils";

type MenuEntry = {
  title: string;
  description: string;
  href?: string;
  icon: Icon;
  soon?: boolean;
  trailing?: string;
};

function displayPhone(value?: string) {
  if (!value) return null;
  const ascii = value
    .replace(/[۰-۹٠-٩]/g, (digit) => {
      const code = digit.charCodeAt(0);
      return String(code >= 0x06f0 ? code - 0x06f0 : code - 0x0660);
    })
    .replace(/[\s()-]/g, "");
  let iranian = ascii;
  if (iranian.startsWith("+98")) iranian = `0${iranian.slice(3)}`;
  else if (iranian.startsWith("0098")) iranian = `0${iranian.slice(4)}`;
  else if (iranian.startsWith("98") && iranian.length === 12) iranian = `0${iranian.slice(2)}`;
  else if (/^9\d{9}$/.test(iranian)) iranian = `0${iranian}`;
  if (!/^09\d{9}$/.test(iranian)) return null;
  return formatPersianDigits(iranian);
}

function usedValue(usage: Record<string, number> | undefined, keys: string[]) {
  if (!usage) return undefined;
  for (const key of keys) {
    const value = usage[key];
    if (typeof value === "number" && Number.isFinite(value) && value >= 0) return value;
  }
  return undefined;
}

function quotaLabel(total: number | null, unit: string, unlimited: boolean, label: string) {
  if (unlimited) return `${label}: نامحدود ${unit}`;
  if (typeof total !== "number" || !Number.isFinite(total)) return `${label}: نامشخص`;
  return `${label}: ${formatPersianNumber(total)} ${unit}`;
}

function consumptionLabel(value: number | undefined) {
  return value === undefined
    ? "مصرف: نامشخص (در انتظار API)"
    : `مصرف: ${formatPersianNumber(value)}`;
}

function MenuLink({ item, onNavigate }: { item: MenuEntry; onNavigate: () => void }) {
  const Icon = item.icon;
  const content = (
    <>
      <span className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-[#ffd8be]/10 bg-white/[0.035] text-[#ffd8be] transition-colors group-hover:border-[#ffd8be]/25 group-hover:bg-[#ffd8be]/10">
        <Icon className="size-5" aria-hidden />
      </span>
      <span className="min-w-0 flex-1 text-right">
        <span className="flex items-center gap-2 text-sm font-semibold text-white">
          <span>{item.title}</span>
          {item.soon && (
            <span className="rounded-full border border-[#e5a87b]/20 bg-[#e5a87b]/10 px-2 py-0.5 text-[10px] font-medium text-[#e5a87b]">
              به‌زودی
            </span>
          )}
        </span>
        <span className="mt-0.5 block truncate text-xs leading-5 text-white/50">
          {item.description}
        </span>
      </span>
      {item.trailing ? (
        <span className="shrink-0 text-xs font-semibold text-[#e5a87b]">{item.trailing}</span>
      ) : (
        <Icons.chevronLeft className="size-4 shrink-0 text-white/30" aria-hidden />
      )}
    </>
  );

  if (!item.href) {
    return (
      <div
        aria-disabled="true"
        title={item.description}
        className="flex min-h-[52px] cursor-not-allowed items-center gap-3 rounded-2xl px-3 py-2 opacity-55"
      >
        {content}
      </div>
    );
  }

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      className="group flex min-h-[52px] touch-manipulation items-center gap-3 rounded-2xl px-3 py-2 outline-none transition-[background-color,transform] active:scale-[0.985] active:bg-white/[0.07] hover:bg-white/[0.045] focus-visible:ring-2 focus-visible:ring-[#ffd8be]/70"
    >
      {content}
    </Link>
  );
}

function QuotaWidget({
  subscription,
  isPending,
  isError,
  isUnavailable,
  onRetry,
  onNavigate
}: {
  subscription?: Subscription;
  isPending: boolean;
  isError: boolean;
  isUnavailable: boolean;
  onRetry: () => void;
  onNavigate: () => void;
}) {
  const usage = subscription?.usage;
  const metrics = [
    {
      label: "آگهی",
      quota: quotaLabel(
        subscription?.listing_quota ?? null,
        "آگهی",
        subscription?.is_unlimited ?? false,
        "سهمیه پلن"
      ),
      consumption: consumptionLabel(usedValue(usage, ["listings_used", "listing_used"])),
      icon: Icons.activity
    },
    {
      label: "پیامک رادار",
      quota: quotaLabel(subscription?.sms_quota ?? null, "پیامک", false, "رادار لید"),
      consumption: consumptionLabel(usedValue(usage, ["sms_used", "radar_sms_used"])),
      icon: Icons.receipt
    }
  ];

  return (
    <section
      aria-label="سهمیه‌های اشتراک"
      className="rounded-2xl border border-[#ffd8be]/12 bg-white/[0.035] p-3.5 shadow-[inset_0_1px_0_rgba(255,216,190,0.04)]"
    >
      <div className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-sm font-bold text-white">سهمیه پیشرفته</p>
          <p className="mt-0.5 text-[11px] text-white/45">از اشتراک فعال حساب</p>
        </div>
        <Icons.activity className="size-5 text-[#ffd8be]" aria-hidden />
      </div>

      {isPending ? (
        <div className="grid grid-cols-2 gap-2" aria-live="polite" aria-label="در حال دریافت سهمیه">
          <div className="h-[58px] animate-pulse rounded-xl bg-white/[0.04]" />
          <div className="h-[58px] animate-pulse rounded-xl bg-white/[0.04]" />
        </div>
      ) : isUnavailable ? (
        <p className="rounded-xl bg-white/[0.03] px-3 py-2.5 text-xs leading-5 text-white/60">
          سهمیه برای این روش ورود در دسترس نیست.
        </p>
      ) : isError || !subscription ? (
        <div className="flex items-center justify-between gap-3 rounded-xl bg-white/[0.03] px-3 py-2.5">
          <p className="text-xs leading-5 text-white/60">خطا در دریافت وضعیت اشتراک</p>
          <Button
            type="button"
            variant="ghost"
            size="xs"
            onClick={onRetry}
            className="shrink-0 text-[#ffd8be] hover:bg-[#ffd8be]/10 hover:text-white"
          >
            تلاش دوباره
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          {metrics.map(({ label, quota, consumption, icon: Icon }) => (
            <div
              key={label}
              className="min-w-0 rounded-xl border border-white/[0.06] bg-[#060b13]/45 px-2.5 py-2"
            >
              <div className="flex items-center gap-1.5 text-[10px] leading-4 text-[#ffd8be]">
                <Icon className="size-3.5 shrink-0 text-[#e5a87b]" aria-hidden />
                <span className="truncate">{quota}</span>
              </div>
              <p className="mt-1 text-[10px] leading-4 text-white/45" dir="rtl">
                {consumption}
              </p>
            </div>
          ))}
        </div>
      )}

      <Link
        href="/dashboard/billing"
        onClick={onNavigate}
        className="mt-3 inline-flex min-h-8 items-center gap-1 text-xs font-semibold text-[#e5a87b] outline-none transition-colors hover:text-[#ffd8be] focus-visible:underline"
      >
        مشاهده جزئیات مصرف
        <Icons.chevronLeft className="size-3.5" aria-hidden />
      </Link>
    </section>
  );
}

export function MobileProfileSheet({
  user,
  planLabel,
  onSignOut
}: {
  user: SessionUser;
  planLabel?: string | null;
  onSignOut: () => Promise<void> | void;
}) {
  const [open, setOpen] = React.useState(false);
  const [signingOut, setSigningOut] = React.useState(false);
  const phone = displayPhone(user.phoneNumber);
  const subscriptionQuery = useCurrentSubscription(open && KEYCLOAK_ENABLED);

  const close = () => setOpen(false);
  const handleSignOut = async () => {
    setSigningOut(true);
    close();
    try {
      await onSignOut();
    } finally {
      setSigningOut(false);
    }
  };

  const primaryItems: MenuEntry[] = [
    {
      title: "سهمیه پیشرفته",
      description: "مدیریت تعداد آگهی‌ها و پیامک‌های رادار",
      href: "/dashboard/billing",
      icon: Icons.activity
    },
    {
      title: "صورتحساب و تمدید اشتراک",
      description: "مشاهده پلن فعلی، پرداخت‌ها و تمدید اشتراک",
      href: "/dashboard/billing",
      icon: Icons.pro
    },
    {
      title: "پرداخت‌ها و فیش‌ها",
      description: "پیگیری پرداخت‌ها و رسیدهای ثبت‌شده",
      href: "/dashboard/billing",
      icon: Icons.receipt
    },
    {
      title: "کیف پول دفتری",
      description: "موجودی کیف پول هنوز از سمت سرور ارائه نشده است.",
      icon: Icons.wallet,
      trailing: "ناموجود"
    },
    {
      title: "شخصی‌سازی حساب",
      description: "مشخصات حساب و تنظیمات امنیتی",
      href: "/dashboard/profile",
      icon: Icons.userCheck
    },
    {
      title: "پلتفرم توسعه‌دهندگان",
      description: "به‌زودی؛ در نسخه بعد فعال می‌شود.",
      icon: Icons.code,
      soon: true
    },
    {
      title: "پشتیبانی شرکت",
      description: "مرکز ارتباطات شکارچی",
      href: "/dashboard/chat",
      icon: Icons.headphones
    }
  ];

  const systemItems: MenuEntry[] = [
    {
      title: "تنظیمات سیستم",
      description: "مدیریت امنیت و تنظیمات حساب",
      href: "/dashboard/profile",
      icon: Icons.settings
    }
  ];

  return (
    <Drawer open={open} onOpenChange={setOpen} swipeDirection="down">
      <DrawerTrigger
        render={
          <Button
            type="button"
            variant="ghost"
            aria-label="بازکردن منوی پروفایل"
            className="relative size-10 rounded-full border border-[#ffd8be]/15 bg-white/[0.025] p-0 transition hover:border-[#ffd8be]/35 hover:bg-[#ffd8be]/10 focus-visible:ring-2 focus-visible:ring-[#ffd8be]/70"
          />
        }
      >
        <span className="rounded-full border border-[#ffd8be]/30 bg-[#ffd8be]/10 p-0.5">
          <Avatar className="size-8">
            <AvatarImage src={user.imageUrl || ""} alt={user.fullName || "پروفایل کاربر"} />
            <AvatarFallback className="bg-[#131b27] text-[#ffd8be]">
              <Icons.user2 className="size-5" aria-hidden />
            </AvatarFallback>
          </Avatar>
        </span>
      </DrawerTrigger>

      <DrawerContent
        overlayClassName="bg-[#060b13]/80 backdrop-blur-md"
        className="max-h-[92dvh] rounded-t-[28px] border-x border-t border-[#ffd8be]/20 bg-gradient-to-b from-[#0e1622]/95 via-[#0a1019]/95 to-[#060b13]/[0.98] p-0 text-white shadow-[0_-20px_50px_rgba(0,0,0,0.8)] backdrop-blur-md supports-[backdrop-filter]:bg-[#060b13]/90 supports-[backdrop-filter]:backdrop-blur-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <DrawerSwipeHandle className="mx-auto mt-3 mb-1 h-4 w-12 touch-pan-x after:!h-1.5 after:!w-12 after:!rounded-full after:!bg-[#ffd8be]/30" />
        <DrawerTitle className="sr-only">منوی حساب کاربری</DrawerTitle>
        <DrawerDescription className="sr-only">اطلاعات حساب، اشتراک و تنظیمات</DrawerDescription>

        <DrawerHeader dir="rtl" className="px-4 pb-3 pt-0 text-right sm:px-5">
          <div className="flex items-center gap-3 rounded-2xl border border-[#ffd8be]/12 bg-white/[0.035] p-3.5">
            <div className="shrink-0 rounded-full border border-[#ffd8be]/30 bg-[#ffd8be]/10 p-1.5">
              <Avatar className="size-12">
                <AvatarImage src={user.imageUrl || ""} alt={user.fullName || "پروفایل کاربر"} />
                <AvatarFallback className="bg-[#131b27] text-[#ffd8be]">
                  <Icons.user2 className="size-7" aria-hidden />
                </AvatarFallback>
              </Avatar>
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-base font-bold text-white">
                {user.fullName || "کاربر شکارچی"}
              </p>
              <p
                className="mt-1 truncate text-sm font-semibold tabular-nums text-white/80"
                dir="rtl"
              >
                {phone || "شماره نامشخص"}
              </p>
            </div>
            <span className="max-w-28 shrink-0 rounded-full border border-[#e5a87b]/25 bg-[#e5a87b]/10 px-2.5 py-1 text-center text-[10px] font-semibold leading-4 text-[#e5a87b]">
              {formatPersianDigits(
                subscriptionQuery.data?.title ??
                  (KEYCLOAK_ENABLED && subscriptionQuery.isPending
                    ? "در حال دریافت پلن"
                    : planLabel || "پلن نامشخص")
              )}
            </span>
            <DrawerClose
              render={
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label="بستن منوی حساب"
                  className="shrink-0 text-white/55 hover:bg-white/10 hover:text-white"
                />
              }
            >
              <Icons.close className="size-4" aria-hidden />
            </DrawerClose>
          </div>
        </DrawerHeader>

        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 pb-2 [scrollbar-width:thin] sm:px-5">
          <QuotaWidget
            subscription={subscriptionQuery.data}
            isPending={KEYCLOAK_ENABLED && subscriptionQuery.isPending}
            isError={KEYCLOAK_ENABLED && subscriptionQuery.isError}
            isUnavailable={!KEYCLOAK_ENABLED}
            onRetry={() => void subscriptionQuery.refetch()}
            onNavigate={close}
          />

          <nav aria-label="گزینه‌های پروفایل" className="mt-3 space-y-1" dir="rtl">
            {primaryItems.map((item) => (
              <MenuLink key={item.title} item={item} onNavigate={close} />
            ))}
          </nav>

          <div className="my-3 border-t border-white/10" />

          <nav aria-label="تنظیمات حساب" className="space-y-1" dir="rtl">
            {systemItems.map((item) => (
              <MenuLink key={item.title} item={item} onNavigate={close} />
            ))}
          </nav>
        </div>

        <div className="shrink-0 border-t border-white/10 px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-2 sm:px-5">
          <Button
            type="button"
            dir="rtl"
            disabled={signingOut}
            onClick={() => void handleSignOut()}
            className="min-h-[52px] w-full justify-start gap-3 rounded-2xl border border-rose-400/15 bg-rose-400/[0.06] px-3 text-rose-300 hover:bg-rose-400/10 hover:text-rose-200 active:scale-[0.99]"
          >
            {signingOut ? (
              <Icons.spinner className="size-5 animate-spin" aria-hidden />
            ) : (
              <Icons.logout className="size-5" aria-hidden />
            )}
            <span className="flex-1 text-right text-sm font-semibold">خروج امن از حساب</span>
          </Button>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
