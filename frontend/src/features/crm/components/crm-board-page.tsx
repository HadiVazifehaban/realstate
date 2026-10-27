"use client";

import PageContainer from "@/components/layout/page-container";
import { BoardStatsStrip } from "./board-stats-strip";
import { BoardToolbar, EMPTY_FILTERS, matchesFilters, type BoardFilters } from "./board-toolbar";
import { LeadBoard } from "./lead-board";
import { LeadDetailDrawer } from "./lead-detail-drawer";
import { LostLeadsDrawer } from "./lost-leads-drawer";
import { NewLeadDialog } from "./new-lead-dialog";
import { LEAD_SOURCE_LABELS, LEAD_STAGE_LABELS, PROPERTY_SOURCES } from "../types";
import * as React from "react";
import { useLeads } from "../hooks";
import type { Actor } from "../types";
import { useAuthContext } from "@/hooks/use-auth";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { LeadSummary } from "../types";
import { Icons } from "@/components/icons";
import "./crm-workspace.css";

/**
 * Provenance legend.
 *
 * Precedence is not decorative: `INTERNAL_USER` outranks a portal scrape in the
 * deduplicator, so a broker judging whether to trust a card reads this row
 * before the price. The audit note is here for the same reason -- moving a
 * card is not a local UI effect, it is an audited state-machine transition.
 *
 * `DELTA` is not listed: the backend `PropertySource` enum has no such member,
 * so there is no data behind it. Adding the portal is a backend enum change
 * first, and the legend picks it up automatically from PROPERTY_SOURCES.
 */
function SourceLegend() {
  return (
    <details className="crm-source-legend rounded-xl border bg-card/60 px-4 py-3 text-xs">
      <summary className="text-muted-foreground cursor-pointer font-medium">
        راهنمای منابع و ثبت تغییرات
      </summary>
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-3">
        {PROPERTY_SOURCES.map((source) => (
          <span key={source} className="text-muted-foreground">
            {LEAD_SOURCE_LABELS[source]}
          </span>
        ))}
        <span className="text-muted-foreground">انتقال‌ها با ممیزی (Audit) ثبت می‌شوند</span>
      </div>
    </details>
  );
}

/**
 * The broker desk.
 *
 * Session claims inform UI affordances; the API independently authorizes every
 * request from its verified principal.
 */
export default function CrmBoardPage() {
  // UI hints come from the actual session. FastAPI independently derives and
  // enforces permissions from the signed principal; never impersonate ADMIN.
  const auth = useAuthContext();
  const apiRole = React.useMemo<Actor["role"]>(() => {
    const roles = auth.roles;
    if (roles.includes("ROLE_ADMIN")) return "ADMIN";
    if (roles.includes("ROLE_SUPERVISOR")) return "SUPERVISOR";
    if (roles.includes("ROLE_AGENCY_MANAGER")) return "OFFICE_MANAGER";
    if (roles.includes("ROLE_SENIOR_BROKER") || roles.includes("ROLE_JUNIOR_BROKER"))
      return "AGENT";
    if (roles.includes("ROLE_OWNER")) return "OWNER";
    if (roles.includes("ROLE_VERIFIED_USER")) return "USER";
    return undefined;
  }, [auth.roles]);
  const actor: Actor = {
    role: apiRole,
    tier: auth.saasTier === "PRO" || auth.saasTier === "ENTERPRISE" ? auth.saasTier : undefined
  };

  const [filters, setFilters] = React.useState<BoardFilters>(EMPTY_FILTERS);
  // The open lead is held by id, not by card: the sheet then always renders the
  // server's current copy, even if the card was dragged in the meantime.
  const [openLeadId, setOpenLeadId] = React.useState<string | null>(null);
  const [view, setView] = React.useState<"kanban" | "table">("kanban");

  // Same query key as the board's own feed, so this is a cache read rather than
  // a second request -- it exists only to give the toolbar an honest count.
  const { data, isPending, isError, isFetching, dataUpdatedAt } = useLeads({}, actor);
  const all = data?.items ?? [];
  const visible = React.useMemo(
    () => all.filter((lead) => matchesFilters(lead, filters)).length,
    [all, filters]
  );

  return (
    <PageContainer>
      <div className="crm-workspace flex min-w-0 flex-col gap-5" dir="rtl">
        <header className="crm-hero rounded-2xl border p-5 sm:p-7">
          <div className="flex flex-col justify-between gap-5 xl:flex-row xl:items-center">
            <div className="flex items-start gap-3 sm:gap-4">
              <div
                className="crm-hero-icon flex size-12 shrink-0 items-center justify-center rounded-2xl border text-primary"
                aria-hidden="true"
              >
                <Icons.kanban className="size-6" />
              </div>
              <div className="min-w-0">
                <p className="mb-2 text-xs font-medium text-primary">مدیریت ارتباط با مشتریان</p>
                <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">میز کار معاملات</h1>
                <p className="mt-2 max-w-2xl text-sm leading-7 text-muted-foreground">
                  از اولین تماس تا معاملهٔ موفق؛ فایل‌ها، بازدیدها و پیگیری‌های دفتر را یک‌جا مدیریت
                  کنید.
                </p>
              </div>
            </div>
            <div className="crm-hero-actions flex flex-wrap items-center gap-2">
              <LostLeadsDrawer actor={actor} />
              <NewLeadDialog actor={actor} />
            </div>
          </div>
          <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-border/70 pt-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-2">
              <Icons.shield className="size-4 text-primary" aria-hidden="true" />
              اطلاعات تماس فقط از مسیر دسترسی مجاز نمایش داده می‌شود
            </span>
            <span role="status" className="flex items-center gap-2">
              <span
                className={`size-1.5 rounded-full ${isError ? "bg-destructive" : isPending || isFetching ? "bg-primary" : "bg-emerald-500"}`}
                aria-hidden="true"
              />
              {isPending ? (
                "در حال دریافت داده‌ها…"
              ) : isError ? (
                "دریافت داده‌ها ناموفق بود"
              ) : isFetching ? (
                "در حال به‌روزرسانی…"
              ) : dataUpdatedAt ? (
                <>
                  آخرین دریافت:{" "}
                  <time dateTime={new Date(dataUpdatedAt).toISOString()}>
                    {new Intl.DateTimeFormat("fa-IR", {
                      hour: "2-digit",
                      minute: "2-digit"
                    }).format(dataUpdatedAt)}
                  </time>
                </>
              ) : (
                "زمان دریافت در دسترس نیست"
              )}
            </span>
          </div>
        </header>
        <section aria-label="خلاصه عملکرد میز کار">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-sm font-semibold">نمای کلی پرونده‌ها</h2>
            <p className="text-xs text-muted-foreground">
              آمار کل میز کار، مستقل از فیلترهای نمایش
            </p>
          </div>
          <BoardStatsStrip actor={actor} />
        </section>
        <section
          className="crm-board-panel min-w-0 rounded-2xl border bg-card/40 p-3 sm:p-5"
          aria-label="پرونده‌ها و پیگیری‌ها"
        >
          <Tabs value={view} onValueChange={(value) => setView(value as "kanban" | "table")}>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold">پرونده‌ها و پیگیری‌ها</h2>
                <p className="mt-1.5 text-xs text-muted-foreground">
                  {view === "kanban"
                    ? "نمای مرحله‌ای؛ انتقال از منوی کارت یا کشیدن و رها کردن"
                    : "نمای فهرستی؛ دسترسی سریع به جزئیات و جلسه‌های ثبت‌شده"}
                </p>
              </div>
              <TabsList aria-label="نوع نمایش پرونده‌ها" className="crm-view-switch">
                <TabsTrigger value="kanban">
                  <Icons.kanban className="size-4" aria-hidden="true" />
                  کانبان
                </TabsTrigger>
                <TabsTrigger value="table">
                  <Icons.dashboard className="size-4" aria-hidden="true" />
                  جدول
                </TabsTrigger>
              </TabsList>
            </div>
            <BoardToolbar
              filters={filters}
              onChange={setFilters}
              visible={visible}
              total={all.length}
            />
            <p className="mb-4 flex items-start gap-2 text-xs leading-6 text-muted-foreground">
              <Icons.info className="mt-1 size-3.5 shrink-0" aria-hidden="true" />
              مبالغ، قیمت آگهی‌اند؛ نه درآمد دفتر یا ارزش قطعی معامله.
            </p>
            <TabsContent value="kanban">
              <LeadBoard actor={actor} filters={filters} onOpenLead={setOpenLeadId} />
            </TabsContent>
            <TabsContent value="table">
              <LeadTable actor={actor} filters={filters} onOpenLead={setOpenLeadId} view={view} />
            </TabsContent>
          </Tabs>
        </section>
        <SourceLegend />
        <LeadDetailDrawer leadId={openLeadId} actor={actor} onClose={() => setOpenLeadId(null)} />
      </div>
    </PageContainer>
  );
}

function LeadTable({
  actor,
  filters,
  onOpenLead,
  view
}: {
  actor: Actor;
  filters: BoardFilters;
  onOpenLead: (leadId: string) => void;
  view: "kanban" | "table";
}) {
  const { data, isPending, isError, error } = useLeads({ limit: 500 }, actor);
  const rows = React.useMemo(
    () => (data?.items ?? []).filter((lead) => matchesFilters(lead, filters)),
    [data, filters]
  );
  const [appointments, setAppointments] = React.useState<Array<{ lead: LeadSummary; at: string }>>(
    []
  );
  React.useEffect(() => {
    let cancelled = false;
    const loadAppointments = async () => {
      const { fetchLead } = await import("../api/client");
      const details = await Promise.all(
        rows.map(async (lead) => {
          try {
            return await fetchLead(lead.id, actor);
          } catch {
            return null;
          }
        })
      );
      if (cancelled) return;
      setAppointments(
        details
          .flatMap((detail) =>
            detail
              ? detail.timeline
                  .filter((event) => event.interaction_type === "VISIT_EVENT" && event.scheduled_at)
                  .map((event) => ({ lead: detail.lead, at: event.scheduled_at! }))
              : []
          )
          .sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime())
      );
    };
    if (view === "table" && rows.length) void loadAppointments();
    else setAppointments([]);
    return () => {
      cancelled = true;
    };
  }, [rows, actor.role, actor.tier, view]);

  if (isPending)
    return (
      <p role="status" className="text-muted-foreground p-8 text-center">
        در حال دریافت پرونده‌ها…
      </p>
    );
  if (isError)
    return (
      <p role="alert" className="text-destructive p-8 text-center">
        {(error as Error).message}
      </p>
    );
  if (rows.length === 0)
    return (
      <p className="text-muted-foreground rounded-lg border p-8 text-center">
        پرونده‌ای با این فیلترها پیدا نشد.
      </p>
    );

  const fa = new Intl.NumberFormat("fa-IR");
  const date = (value: string) =>
    new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium" }).format(new Date(value));
  return (
    <div className="crm-lead-table border-border w-full overflow-x-auto rounded-xl border">
      <table className="w-full min-w-[760px] text-right text-sm">
        <caption className="sr-only">فهرست پرونده‌ها، مرحلهٔ پیگیری و قیمت آگهی</caption>
        <thead className="bg-muted/50 text-muted-foreground text-xs">
          <tr>
            <th className="p-3">پرونده و ملک</th>
            <th className="p-3">مرحله</th>
            <th className="p-3">موقعیت</th>
            <th className="p-3">اقدام / آخرین تغییر</th>
            <th className="p-3">قیمت آگهی</th>
            <th className="p-3">منبع</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((lead) => (
            <tr key={lead.id} className="border-border border-t">
              <td className="p-3">
                <button
                  type="button"
                  className="text-primary text-right font-medium hover:underline"
                  onClick={() => onOpenLead(lead.id)}
                >
                  {lead.title || "ملک بدون عنوان"}
                </button>
                <span className="text-muted-foreground mt-1 block font-mono text-[10px]" dir="ltr">
                  {lead.id.slice(0, 8)}
                </span>
              </td>
              <td className="p-3">
                <span className="inline-flex rounded-full border bg-muted/40 px-2.5 py-1 text-xs">
                  {LEAD_STAGE_LABELS[lead.stage]}
                </span>
              </td>
              <td className="p-3">
                {[lead.neighborhood, lead.city].filter(Boolean).join("، ") || "—"}
              </td>
              <td className="p-3">{date(lead.updated_at)}</td>
              <td className="p-3 tabular-nums">
                {lead.total_price == null ? "ثبت نشده" : `${fa.format(lead.total_price)} تومان`}
              </td>
              <td className="p-3">{lead.source ? LEAD_SOURCE_LABELS[lead.source] : "نامشخص"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-muted-foreground border-border border-t px-3 py-2 text-[11px]">
        API فعلی پروندهٔ قراردادی، طرفین، مسئول تخصیص‌یافته، پرداخت و کمیسیون را ارائه نمی‌کند؛ این
        ستون‌ها جعل یا از اطلاعات ملک استنتاج نشده‌اند.
      </p>
      <section className="border-border border-t p-3" aria-labelledby="crm-appointments-heading">
        <h2 id="crm-appointments-heading" className="text-sm font-semibold">
          جلسه‌های ثبت‌شده
        </h2>
        <p className="text-muted-foreground mt-1 text-xs">
          رویدادهای بازدید ثبت‌شده در تایم‌لاین؛ بدون ارسال یادآوری بیرونی.
        </p>
        {appointments.length === 0 ? (
          <p className="text-muted-foreground py-3 text-xs">
            جلسهٔ ثبت‌شده‌ای برای فهرست فعلی در دسترس نیست.
          </p>
        ) : (
          <ul className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {appointments.map(({ lead, at }, index) => (
              <li
                key={`${lead.id}-${at}-${index}`}
                className="bg-muted/30 flex items-center justify-between gap-2 rounded-md p-2 text-xs"
              >
                <button
                  type="button"
                  className="text-primary truncate text-right hover:underline"
                  onClick={() => onOpenLead(lead.id)}
                >
                  {lead.title || lead.neighborhood || "ملک بدون عنوان"}
                </button>
                <time className="shrink-0" dateTime={at}>
                  {new Intl.DateTimeFormat("fa-IR", {
                    dateStyle: "short",
                    timeStyle: "short"
                  }).format(new Date(at))}
                </time>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
