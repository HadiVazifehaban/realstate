"use client";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Icons } from "@/components/icons";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { MobileProfileSheet } from "@/components/navigation/MobileProfileSheet";
import { useAuthContext, useAuthSignOut } from "@/hooks/use-auth";
import { useIsMobile } from "@/hooks/use-mobile";
import { useRouter } from "next/navigation";
import { SidebarMenuButton } from "@/components/ui/sidebar";
import { accountNavItems } from "@/config/nav-config";
import { useAuthOrganization } from "@/hooks/use-auth";
import { useNotificationStore } from "@/features/notifications/utils/store";

// Priority matters when the realm issues several roles for the same user.
const ROLE_LABELS = [
  ["ROLE_ADMIN", "مدیر سامانه"],
  ["ROLE_SUPERVISOR", "سرپرست"],
  ["ROLE_AGENCY_MANAGER", "مدیر دفتر"],
  ["ROLE_SENIOR_BROKER", "مشاور ارشد"],
  ["ROLE_JUNIOR_BROKER", "مشاور"],
  ["ROLE_DATA_ANALYST", "تحلیل‌گر داده"],
  ["ROLE_OWNER", "مالک"],
  ["ROLE_VERIFIED_USER", "کاربر تأییدشده"],
  ["ROLE_UNVERIFIED_USER", "کاربر تأییدنشده"]
] as const;

const MENU_ITEM_CLASS =
  "cursor-pointer gap-3 rounded-none px-4 py-2.5 text-xs text-foreground transition-colors hover:bg-[var(--brand-e5a87b)]/10 hover:text-primary focus:bg-[var(--brand-e5a87b)]/10 focus:text-primary";

export function UserNav({
  placement = "header",
  mobileOnly = false
}: {
  placement?: "header" | "sidebar" | "landing";
  mobileOnly?: boolean;
}) {
  const { user, saasTier, roles } = useAuthContext();
  const signOut = useAuthSignOut();
  const router = useRouter();
  const isMobile = useIsMobile();
  const organization = useAuthOrganization();
  const unreadCount = useNotificationStore(
    (state) => state.notifications.filter((notification) => notification.status === "unread").length
  );
  const inSidebar = placement === "sidebar";
  const [open, setOpen] = React.useState(false);
  const [signingOut, setSigningOut] = React.useState(false);
  const [signOutError, setSignOutError] = React.useState("");

  const handleSignOut = async () => {
    if (signingOut) return;
    setSigningOut(true);
    setSignOutError("");
    try {
      await signOut({ redirectUrl: "/" });
    } catch {
      setSignOutError("خروج از حساب انجام نشد؛ دوباره تلاش کنید.");
      setOpen(true);
    } finally {
      setSigningOut(false);
    }
  };

  if (mobileOnly && !isMobile) return null;
  if (user) {
    if (isMobile) {
      return (
        <MobileProfileSheet
          user={user}
          planLabel={saasTier}
          onSignOut={() => signOut({ redirectUrl: "/" })}
        />
      );
    }

    return (
      <DropdownMenu open={open} onOpenChange={setOpen}>
        <DropdownMenuTrigger
          render={
            inSidebar ? (
              <SidebarMenuButton
                size="lg"
                tooltip={`${user.fullName || "کاربر شکارچی"} — ${ROLE_LABELS.find(([role]) => roles.includes(role))?.[1] ?? "حساب کاربری"}`}
                aria-label="بازکردن منوی حساب کاربری"
                dir="rtl"
                className="gap-2 data-open:bg-sidebar-accent data-open:text-sidebar-accent-foreground"
              />
            ) : (
              <Button
                variant="ghost"
                aria-label="بازکردن منوی حساب کاربری"
                dir="rtl"
                className="group h-auto max-w-64 gap-3 rounded-full border border-primary/20 bg-background/60 px-3.5 py-1.5 text-primary shadow-lg backdrop-blur-md transition-all hover:border-primary/60 hover:bg-background/80 focus-visible:ring-[var(--brand-ffd8be)]/60"
              />
            )
          }
        >
          <Avatar
            className={
              inSidebar
                ? "size-8 shrink-0 rounded-md"
                : "size-8 shrink-0 rounded-full border border-primary/30 shadow-md"
            }
          >
            <AvatarImage src={user.imageUrl || ""} alt="" />
            <AvatarFallback
              className={
                inSidebar
                  ? "rounded-md bg-sidebar-accent text-xs font-semibold text-sidebar-accent-foreground"
                  : "rounded-full bg-gradient-to-br from-primary to-primary text-xs font-black text-primary-foreground"
              }
            >
              {Array.from(user.fullName?.trim() || "ش")[0]}
            </AvatarFallback>
          </Avatar>
          <span
            className={
              inSidebar
                ? "min-w-0 flex-1 text-right group-data-[collapsible=icon]:hidden"
                : "hidden min-w-0 text-right sm:block"
            }
          >
            <span
              className={
                inSidebar
                  ? "block truncate text-xs font-medium leading-5 text-sidebar-foreground"
                  : "block truncate text-xs font-bold leading-5 text-primary transition-colors group-hover:text-foreground"
              }
            >
              {user.fullName || "کاربر شکارچی"}
            </span>
            <span
              className={
                inSidebar
                  ? "block truncate text-[10px] leading-4 text-sidebar-foreground/70"
                  : "block truncate text-[10px] leading-4 text-muted-foreground"
              }
            >
              {ROLE_LABELS.find(([role]) => roles.includes(role))?.[1] ?? "حساب کاربری"}
            </span>
          </span>
          <Icons.chevronDown
            aria-hidden
            className={`size-3 shrink-0 motion-reduce:transition-none ${inSidebar ? "ms-auto text-sidebar-foreground/70 group-data-[collapsible=icon]:hidden" : "text-primary"} transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          />
        </DropdownMenuTrigger>
        <DropdownMenuContent
          dir="rtl"
          aria-label="منوی حساب کاربری"
          className={
            inSidebar
              ? "w-64 max-w-[calc(100vw-2rem)] rounded-md bg-sidebar p-1 text-right text-sidebar-foreground ring-1 ring-sidebar-border motion-reduce:animate-none"
              : "w-64 max-w-[calc(100vw-2rem)] rounded-2xl border border-primary/30 bg-background/90 px-0 py-2 text-right text-foreground shadow-2xl ring-0 backdrop-blur-xl duration-200"
          }
          align="end"
          side={inSidebar ? "left" : "bottom"}
          sideOffset={inSidebar ? 4 : 10}
        >
          {placement !== "header" ? (
            <DropdownMenuGroup>
              {accountNavItems
                .filter((item) => !item.access?.requireOrg || organization)
                .map((item) => {
                  const Icon = Icons[item.icon ?? "account"];
                  return (
                    <DropdownMenuItem
                      key={item.url}
                      onClick={() => router.push(item.url)}
                      className="cursor-pointer gap-2 rounded-md px-2 py-2 text-xs text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus:bg-sidebar-accent focus:text-sidebar-accent-foreground"
                    >
                      <Icon aria-hidden className="size-4 text-sidebar-foreground/70" />
                      <span>{item.url === "/dashboard/profile" ? "حساب کاربری" : item.title}</span>
                      {item.url === "/dashboard/notifications" && unreadCount > 0 && (
                        <span
                          aria-label={`${unreadCount} اعلان خوانده‌نشده`}
                          className="ms-auto rounded-md bg-sidebar-accent px-1.5 text-[10px] tabular-nums text-sidebar-accent-foreground"
                        >
                          {new Intl.NumberFormat("fa-IR").format(unreadCount)}
                        </span>
                      )}
                    </DropdownMenuItem>
                  );
                })}
              <DropdownMenuItem
                disabled={signingOut}
                onClick={() => void handleSignOut()}
                className="cursor-pointer gap-2 rounded-md px-2 py-2 text-xs text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus:bg-sidebar-accent focus:text-sidebar-accent-foreground"
              >
                <Icons.logout aria-hidden className="size-4 text-sidebar-foreground/70" />
                {signingOut ? "در حال خروج…" : "خروج"}
              </DropdownMenuItem>
            </DropdownMenuGroup>
          ) : (
            <>
              <DropdownMenuGroup>
                <DropdownMenuLabel className="border-b border-primary/15 bg-[var(--brand-e5a87b)]/[0.03] px-4 py-3 font-normal">
                  <div className="min-w-0 space-y-1">
                    <p
                      className="truncate text-sm font-extrabold leading-6 text-primary"
                      title={user.fullName || "کاربر شکارچی"}
                    >
                      {user.fullName || "کاربر شکارچی"}
                    </p>
                    <p
                      dir="auto"
                      className="truncate text-right font-mono text-[11px] leading-5 text-muted-foreground"
                      title={
                        user.emailAddresses[0]?.emailAddress || user.phoneNumber || "حساب کاربری"
                      }
                    >
                      {user.emailAddresses[0]?.emailAddress || user.phoneNumber || "حساب کاربری"}
                    </p>
                  </div>
                </DropdownMenuLabel>
              </DropdownMenuGroup>
              <DropdownMenuGroup className="py-1">
                <DropdownMenuItem
                  className={MENU_ITEM_CLASS}
                  onClick={() => router.push("/dashboard/notifications")}
                >
                  <Icons.notification aria-hidden className="size-4 text-primary" />
                  <span>اعلان‌ها</span>
                  {unreadCount > 0 && (
                    <span
                      aria-label={`${unreadCount} اعلان خوانده‌نشده`}
                      className="ms-auto flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-medium text-destructive-foreground"
                    >
                      {new Intl.NumberFormat("fa-IR").format(unreadCount)}
                    </span>
                  )}
                </DropdownMenuItem>
                <DropdownMenuItem
                  className={MENU_ITEM_CLASS}
                  onClick={() => router.push("/dashboard/properties")}
                >
                  <Icons.crosshair aria-hidden className="size-4 shrink-0 text-primary" />
                  رادار شکار قیمت
                </DropdownMenuItem>
                <DropdownMenuItem
                  className={MENU_ITEM_CLASS}
                  onClick={() => router.push("/dashboard/profile")}
                >
                  <Icons.settings aria-hidden className="size-4 shrink-0 text-primary" />
                  تنظیمات حساب کاربری
                </DropdownMenuItem>
                <DropdownMenuItem
                  className={MENU_ITEM_CLASS}
                  onClick={() => router.push("/dashboard/roles")}
                >
                  <Icons.shield aria-hidden className="size-4 shrink-0 text-primary" />
                  امنیت و سطوح دسترسی (RBAC)
                </DropdownMenuItem>
                <DropdownMenuItem
                  className={MENU_ITEM_CLASS}
                  onClick={() => router.push("/dashboard/billing")}
                >
                  <Icons.billing aria-hidden className="size-4 shrink-0 text-primary" />
                  اشتراک و صورتحساب‌ها
                </DropdownMenuItem>
                <DropdownMenuItem
                  className={MENU_ITEM_CLASS}
                  onClick={() => router.push("/dashboard/network/commissions")}
                >
                  <Icons.split aria-hidden className="size-4 shrink-0 text-primary" />
                  کمیسیون و تسویه
                </DropdownMenuItem>
              </DropdownMenuGroup>
              <DropdownMenuSeparator className="mx-0 my-1 bg-[var(--brand-e5a87b)]/15" />
              <DropdownMenuGroup>
                <DropdownMenuItem
                  disabled={signingOut}
                  className="cursor-pointer gap-3 rounded-none px-4 py-2.5 text-xs text-rose-400 transition-colors hover:bg-rose-500/10 focus:bg-rose-500/10 focus:text-rose-300"
                  onClick={() => void handleSignOut()}
                >
                  <Icons.logout aria-hidden className="size-4 shrink-0" />
                  {signingOut ? "در حال خروج…" : "خروج امن از حساب"}
                </DropdownMenuItem>
              </DropdownMenuGroup>
            </>
          )}
          {signOutError && (
            <p role="alert" className="px-4 py-2 text-xs leading-5 text-rose-300">
              {signOutError}
            </p>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }
  return null;
}
