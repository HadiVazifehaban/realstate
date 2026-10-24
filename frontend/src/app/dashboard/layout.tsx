import KBar from "@/components/kbar";
import { DashboardShell } from "@/components/layout/dashboard-shell";
import { SidebarProvider } from "@/components/ui/sidebar";
import { auth } from "@clerk/nextjs/server";
import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import { AUTH_BYPASS_ENABLED, KEYCLOAK_ENABLED } from "@/lib/utils";
import { ApprovalGate } from "@/features/auth/components/approval-gate";
import { SessionExpiryGuard } from "@/features/auth/components/session-expiry-guard";

export const metadata: Metadata = {
  title: "داشبورد مدیریتی شکارچی | SHEKARCHI",
  description: "سامانهٔ مدیریت و تحلیل بازار املاک شکارچی",
  robots: {
    index: false,
    follow: false
  }
};

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const requestHeaders = await headers();
  const isPublicRoute = requestHeaders.get("x-shekarchi-public-route") === "true";
  // Gate the whole /dashboard segment: redirect to sign-in when signed out.
  // The bypass is local-dev only — see AUTH_BYPASS_ENABLED in lib/utils.
  // Clerk guards the session; Keycloak mode is checked client-side by
  // ApprovalGate, because the KYC claim lives on the access token rather than
  // in a cookie this layout can read.
  if (!isPublicRoute && !AUTH_BYPASS_ENABLED && !KEYCLOAK_ENABLED) {
    await auth.protect();
  }
  // Retain provider compatibility for the existing office/account controls.
  const cookieStore = await cookies();
  const defaultOpen = cookieStore.get("sidebar_state")?.value === "true";
  return (
    <KBar>
      <SessionExpiryGuard />
      <SidebarProvider defaultOpen={defaultOpen} side="right">
        <a
          href="#main-content"
          className="bg-background ring-ring sr-only rounded-md px-3 py-2 text-sm font-medium shadow focus:not-sr-only focus:absolute focus:top-2 focus:start-2 focus:z-50 focus:ring-2"
        >
          Skip to content
        </a>
        <DashboardShell>
          <ApprovalGate publicRoute={isPublicRoute}>{children}</ApprovalGate>
        </DashboardShell>
      </SidebarProvider>
    </KBar>
  );
}
