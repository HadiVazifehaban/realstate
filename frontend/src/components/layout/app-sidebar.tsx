"use client";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
  useSidebar
} from "@/components/ui/sidebar";

import { Logo } from "@/components/brand/logo";
import { Badge } from "@/components/ui/badge";
import { UserAvatarProfile } from "@/components/user-avatar-profile";
import { navGroups } from "@/config/nav-config";
import { useAuthOrganization, useAuthSignOut, useAuthUser } from "@/hooks/use-auth";
import { useFilteredNavGroups } from "@/hooks/use-nav";
import { useIsMobile } from "@/hooks/use-mobile";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import * as React from "react";
import { Fragment } from "react";
import { Icons } from "../icons";
import { OrgSwitcher } from "../org-switcher";
import { ErrorBoundary } from "@/components/ui/error-boundary";

/**
 * نشان وضعیت آیتم‌های منو
 */
function NavBadge({ text }: { text: string }) {
  return (
    <Badge
      variant="outline"
      className="ms-auto me-1 h-4 shrink-0 border-sidebar-border/70 px-1.5 text-[10px] font-normal text-sidebar-foreground/70"
    >
      {text}
    </Badge>
  );
}

export default function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();

  const { state } = useSidebar();

  const user = useAuthUser();
  const organization = useAuthOrganization();
  const signOut = useAuthSignOut();
  const filteredGroups = useFilteredNavGroups(navGroups);

  const isCollapsed = state === "collapsed";
  const isMobile = useIsMobile();

  const [openItems, setOpenItems] = React.useState<Set<string>>(new Set());

  // Mobile viewports: replace the legacy drawer/sidebar with the fixed bottom
  // navigation bar (MobileBottomNav). The sidebar is not rendered here so the
  // mobile layout stays clean and uncluttered.
  if (isMobile) {
    return null;
  }

  const toggleItem = (title: string) => {
    setOpenItems((prev) => {
      const next = new Set(prev);
      if (next.has(title)) next.delete(title);
      else next.add(title);
      return next;
    });
  };

  const getItemTitle = (item: { title: string; description?: string | null }) => {
    return item.description ? `${item.title} — ${item.description}` : item.title;
  };

  return (
    <Sidebar collapsible="icon">
      <SidebarRail />
      <ErrorBoundary>
        <SidebarHeader className="gap-0 p-0">
          <Link
            href="/dashboard/overview"
            aria-label="شکارچی — داشبورد"
            title={isCollapsed ? "شکارچی — داشبورد" : undefined}
            className="flex w-full shrink-0 items-center justify-center overflow-visible px-0 py-6 outline-hidden focus-visible:ring-2 focus-visible:ring-sidebar-ring"
          >
            <Logo
              size={160}
              className="transition-[width,height] duration-200 ease-linear group-data-[collapsible=icon]:[--logo-size:2.5rem]"
            />
          </Link>

          <OrgSwitcher />
        </SidebarHeader>

        <SidebarContent className="overflow-x-hidden">
          {filteredGroups.map((group) => (
            <SidebarGroup key={group.label || "ungrouped"} className="py-0">
              {group.label && <SidebarGroupLabel>{group.label}</SidebarGroupLabel>}

              <SidebarMenu>
                {group.items.map((item) => {
                  const IconComponent = item.icon
                    ? ((Icons[item.icon] as React.ComponentType<{ className?: string }> | undefined) ?? Icons.logo)
                    : Icons.logo;

                  const hasChildren = Boolean(item.items && item.items.length > 0);

                  const isItemActive =
                    Boolean(item.url) &&
                    (pathname === item.url ||
                      Boolean(
                        item.items?.some(
                          (subItem) => Boolean(subItem.url) && pathname === subItem.url
                        )
                      ));

                  const safeNavigate = (url?: string) => {
                    if (!url) return;
                    router.push(url);
                  };

                  if (hasChildren) {
                    if (isCollapsed) {
                      return (
                        <SidebarMenuItem key={item.title}>
                          <DropdownMenu>
                            <DropdownMenuTrigger
                              render={<SidebarMenuButton tooltip={item.title} isActive={isItemActive} />}
                            >
                              <IconComponent className="h-4 w-4 shrink-0 text-sidebar-foreground/70" />
                            </DropdownMenuTrigger>
                            <DropdownMenuContent side="right" align="start" sideOffset={4}>
                              <DropdownMenuLabel>{item.title}</DropdownMenuLabel>
                              <DropdownMenuSeparator />
                              {item.items?.map((subItem) => {
                                const SubIconComponent = subItem.icon
                                  ? ((Icons[subItem.icon] as React.ComponentType<{ className?: string }> | undefined) ?? Icons.logo)
                                  : null;

                                return (
                                  <DropdownMenuItem
                                    key={subItem.title}
                                    disabled={Boolean(subItem.disabled)}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      if (!subItem.disabled && subItem.url) {
                                        router.push(subItem.url);
                                      }
                                    }}
                                  >
                                    {SubIconComponent && <SubIconComponent className="h-4 w-4 shrink-0 text-sidebar-foreground/70" />}
                                    <span>{subItem.title}</span>
                                    {(subItem.badge || subItem.disabled) && (
                                      <NavBadge text={subItem.badge ?? "به‌زودی"} />
                                    )}
                                  </DropdownMenuItem>
                                );
                              })}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </SidebarMenuItem>
                      );
                    }

                    return (
                      <SidebarMenuItem key={item.title}>
                        <SidebarMenuButton
                          tooltip={item.title}
                          isActive={isItemActive || openItems.has(item.title)}
                          onClick={() => toggleItem(item.title)}
                        >
                          <IconComponent className="h-4 w-4 shrink-0 text-sidebar-foreground/70" />
                          <span>{item.title}</span>
                          <Icons.chevronRight
                            className="ms-auto h-4 w-4 shrink-0 transition-transform duration-200 text-sidebar-foreground/50"
                            style={{
                              transform: openItems.has(item.title)
                                ? "rotate(90deg)"
                                : "rotate(0deg)"
                            }}
                          />
                        </SidebarMenuButton>
                        {openItems.has(item.title) && (
                          <SidebarMenuSub className="mt-1">
                            {item.items?.map((subItem) => {
                              const SubIconComponent = subItem.icon
                                ? ((Icons[subItem.icon] as React.ComponentType<{ className?: string }> | undefined) ?? Icons.logo)
                                : null;

                              return (
                                <SidebarMenuSubItem key={subItem.title}>
                                  {subItem.disabled ? (
                                    <SidebarMenuSubButton
                                      aria-disabled
                                      className="cursor-not-allowed opacity-70"
                                    >
                                      {SubIconComponent && <SubIconComponent className="h-4 w-4 shrink-0 text-sidebar-foreground/70" />}
                                      <span>{subItem.title}</span>

                                      <NavBadge text={subItem.badge ?? "به‌زودی"} />
                                    </SidebarMenuSubButton>
                                  ) : (
                                    <SidebarMenuSubButton
                                      isActive={pathname === subItem.url}
                                      onClick={() => safeNavigate(subItem.url)}
                                    >
                                      {SubIconComponent && <SubIconComponent className="h-4 w-4 shrink-0 text-sidebar-foreground/70" />}
                                      <span>{subItem.title}</span>

                                      {subItem.badge && <NavBadge text={subItem.badge} />}
                                    </SidebarMenuSubButton>
                                  )}
                                </SidebarMenuSubItem>
                              );
                            })}
                          </SidebarMenuSub>
                        )}
                      </SidebarMenuItem>
                    );
                  }

                  return (
                    <SidebarMenuItem key={item.title}>
                      {item.disabled ? (
                        <SidebarMenuButton
                          aria-disabled
                          title={isCollapsed ? getItemTitle(item) : undefined}
                          className="cursor-not-allowed opacity-70"
                        >
                          <IconComponent className="h-4 w-4 shrink-0 text-sidebar-foreground/70" />
                          <span>{item.title}</span>

                          <NavBadge text={item.badge ?? "به‌زودی"} />
                        </SidebarMenuButton>
                      ) : (
                        <SidebarMenuButton
                          title={isCollapsed ? item.title : undefined}
                          isActive={pathname === item.url}
                          onClick={() => safeNavigate(item.url)}
                        >
                          <IconComponent className="h-4 w-4 shrink-0 text-sidebar-foreground/70" />
                          <span>{item.title}</span>

                          {item.badge && <NavBadge text={item.badge} />}
                        </SidebarMenuButton>
                      )}
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroup>
          ))}
        </SidebarContent>

        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              {/* Separator line */}
              <div className="h-px bg-border mx-2" />

              {/* User name with link to profile */}
              <SidebarMenuButton
                onClick={() => router.push("/dashboard/profile")}
                tooltip="پروفایل"
                size="sm"
              >
                <Icons.account className="h-4 w-4 shrink-0 text-sidebar-foreground/70" />
                <span>{user ? "کاربر" : "مهمان"}</span>
              </SidebarMenuButton>

              {/* Other menu items */}
              {organization && (
                <SidebarMenuButton
                  onClick={() => router.push("/dashboard/billing")}
                  tooltip="امور مالی"
                  size="sm"
                >
                  <Icons.creditCard className="h-4 w-4 shrink-0 text-sidebar-foreground/70" />
                  <span>امور مالی</span>
                </SidebarMenuButton>
              )}

              <SidebarMenuButton
                onClick={() => router.push("/dashboard/notifications")}
                tooltip="اعلان‌ها"
                size="sm"
              >
                <Icons.notification className="h-4 w-4 shrink-0 text-sidebar-foreground/70" />
                <span>اعلان‌ها</span>
              </SidebarMenuButton>

              <SidebarMenuButton
                onClick={async () => {
                  await signOut({ redirectUrl: "/auth/sign-in" });
                }}
                tooltip="خروج"
                size="sm"
              >
                <Icons.logout aria-hidden className="h-4 w-4 shrink-0 text-sidebar-foreground/70" />
                <span>خروج</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>

        <SidebarRail />
      </ErrorBoundary>
    </Sidebar>
  );
}
