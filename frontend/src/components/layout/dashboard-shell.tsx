"use client";

import Header from "./header";
import { InfoSidebar } from "./info-sidebar";
import { InfobarProvider } from "@/components/ui/infobar";

/** Shared full-width shell; navigation lives exclusively in the top header. */
export function DashboardShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="dashboard-horizontal-shell min-w-0 w-full flex flex-col">
      <Header />
      <main
        id="main-content"
        tabIndex={-1}
        className="scroll-mt-40 min-w-0 w-full flex flex-1 flex-col"
      >
        <InfobarProvider defaultOpen={false}>
          {children}
          <InfoSidebar side="left" />
        </InfobarProvider>
      </main>
    </div>
  );
}
