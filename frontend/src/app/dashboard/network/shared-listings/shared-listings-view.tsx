"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { IconEyeOff, IconMapPin, IconRefresh, IconSearch, IconTrash } from "@tabler/icons-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger
} from "@/components/ui/alert-dialog";

import { useAuthContext } from "@/hooks/use-auth";
import { useDebounce } from "@/hooks/use-debounce";
import { useExtendShare, useRevokeShare, useInfiniteShares } from "@/features/network/hooks";
import {
  formatJalali,
  ListEmpty,
  ListError,
  ListSkeleton,
  ShareStatusBadge
} from "@/features/network/components/shared";
import {
  SHARE_MODE_LABELS,
  type Share,
  type ShareMode,
  type ShareStatus
} from "@/features/network/types";
import { NetworkApiError } from "@/features/network/api/client";
import { toPersianDigits } from "@/lib/utils";

const PAGE_SIZE = 50;
const STATUS_FILTERS: { value: ShareStatus | "ALL"; label: string }[] = [
  { value: "ALL", label: "همه" },
  { value: "ACTIVE", label: "فعال" },
  { value: "EXPIRED", label: "منقضی‌شده" },
  { value: "REVOKED", label: "لغوشده" },
  { value: "PENDING", label: "در انتظار" }
];

/** فهرست اشتراک‌های ارسالی و دریافتی، همراه مدیریت موجود اشتراک‌ها. */
export function SharedListingsView() {
  const { tenantId: agencyId, isLoading } = useAuthContext();
  if (isLoading) return <ListSkeleton rows={4} />;
  if (!agencyId)
    return (
      <ListEmpty
        title="دفتر شما شناسایی نشد"
        description="برای دیدن فایل‌های اشتراکی، باید با حساب دفتر وارد شده باشید."
      />
    );
  return <AgencyShares key={agencyId} agencyId={agencyId} />;
}

function AgencyShares({ agencyId }: { agencyId: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const direction = searchParams.get("direction") === "incoming" ? "incoming" : "outgoing";
  const status =
    STATUS_FILTERS.find((filter) => filter.value === searchParams.get("status"))?.value ?? "ALL";
  const urlQuery = searchParams.get("q") ?? "";
  const [query, setQuery] = React.useState(urlQuery);
  React.useEffect(() => setQuery(urlQuery), [urlQuery]);
  const debouncedQuery = useDebounce(query, 300).trim().toLocaleLowerCase("fa-IR");
  const updateParams = (changes: Record<string, string | null>) => {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value) params.set(key, value);
      else params.delete(key);
    }
    router.replace(`${pathname}${params.size ? `?${params}` : ""}`, { scroll: false });
  };
  const shares = useInfiniteShares({
    agencyId,
    direction,
    status: status === "ALL" ? undefined : status
  });
  const forbidden = shares.error instanceof NetworkApiError && shares.error.status === 403;
  const loaded = forbidden
    ? []
    : [...new Map((shares.data?.pages.flat() ?? []).map((share) => [share.id, share])).values()];
  const filtered = loaded.filter((share) => matchesSearch(share, debouncedQuery));
  const revoke = useRevokeShare();
  const extend = useExtendShare();
  const mutationLock = React.useRef(false);
  const manage = async (share: Share, action: "extend" | "revoke") => {
    if (mutationLock.current || share.source_agency_id !== agencyId) return;
    mutationLock.current = true;
    try {
      if (action === "extend") await extend.mutateAsync({ shareId: share.id, days: 30 });
      else await revoke.mutateAsync({ shareId: share.id });
    } catch {
      // Mutation hooks display the server error; no optimistic success.
    } finally {
      mutationLock.current = false;
    }
  };

  return (
    <div className="space-y-5">
      <Card>
        <CardContent className="space-y-4 p-4 sm:p-5">
          <div>
            <h2 className="text-lg font-semibold">فایل‌های اشتراکی</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              جست‌وجو و بررسی فایل‌های قابل همکاری در شبکه دفاتر شکارچی
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative w-full sm:max-w-sm">
              <IconSearch className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                aria-label="جست‌وجو در فایل‌های اشتراکی"
                className="h-10 pr-9"
                onChange={(event) => setQuery(event.target.value)}
                onBlur={() => updateParams({ q: query.trim() || null })}
                onKeyDown={(event) => {
                  if (event.key === "Enter") updateParams({ q: query.trim() || null });
                }}
                placeholder="جست‌وجو با کد فایل، یادداشت یا مسئول"
                value={query}
              />
            </div>
            <div className="flex flex-wrap gap-1.5">
              {STATUS_FILTERS.map((filter) => (
                <Button
                  key={filter.value}
                  size="sm"
                  variant={status === filter.value ? "default" : "ghost"}
                  onClick={() =>
                    updateParams({
                      status: filter.value === "ALL" ? null : filter.value,
                      q: query.trim() || null
                    })
                  }
                >
                  {filter.label}
                </Button>
              ))}
            </div>
          </div>
          {(query || status !== "ALL") && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setQuery("");
                updateParams({ q: null, status: null });
              }}
            >
              پاک‌کردن فیلترها
            </Button>
          )}
          <p className="text-xs text-muted-foreground">
            جست‌وجو فقط در موارد بارگذاری‌شده انجام می‌شود؛ برای جست‌وجوی بیشتر، موارد بعدی را بارگذاری
            کنید.
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <SummaryCard label="اشتراک‌های بارگذاری‌شده" value={loaded.length} />
            <SummaryCard
              label="فعال در موارد بارگذاری‌شده"
              value={loaded.filter((share) => share.status === "ACTIVE").length}
            />
            <SummaryCard
              label="منقضی در موارد بارگذاری‌شده"
              value={loaded.filter((share) => share.status === "EXPIRED").length}
            />
            <SummaryCard
              label="در انتظار در موارد بارگذاری‌شده"
              value={loaded.filter((share) => share.status === "PENDING").length}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            آمار مربوط به موارد بارگذاری‌شده در جهت و وضعیت انتخابی است، نه کل شبکه.
          </p>
        </CardContent>
      </Card>
      <Tabs
        value={direction}
        onValueChange={(value) => {
          if (value === "incoming" || value === "outgoing") {
            updateParams({
              direction: value === "outgoing" ? null : value,
              q: query.trim() || null
            });
          }
        }}
      >
        <TabsList>
          <TabsTrigger value="outgoing">فایل‌های دفتر ما</TabsTrigger>
          <TabsTrigger value="incoming">فایل‌های شبکه</TabsTrigger>
        </TabsList>
        <TabsContent value={direction} className="mt-4">
          {shares.error instanceof NetworkApiError && shares.error.status === 403 ? (
            <ListEmpty title="دسترسی مجاز نیست" description={shares.error.message} />
          ) : (
            <ShareList
              shares={filtered}
              loading={shares.isPending}
              error={shares.isError && !shares.data}
              emptyTitle={
                debouncedQuery
                  ? "نتیجه‌ای در موارد بارگذاری‌شده پیدا نشد"
                  : status !== "ALL"
                    ? "اشتراکی با این وضعیت پیدا نشد"
                    : "اشتراکی در دسترس نیست"
              }
              emptyDescription="فیلترها را تغییر دهید یا موارد بیشتری بارگذاری کنید."
              refetch={() => void shares.refetch()}
              canLoadMore={shares.hasNextPage && !shares.isFetchNextPageError}
              loadingMore={shares.isFetching}
              onLoadMore={() => {
                if (!shares.isFetching) void shares.fetchNextPage();
              }}
              onRevoke={(share) => void manage(share, "revoke")}
              onExtend={(share) => void manage(share, "extend")}
              mutationPending={revoke.isPending || extend.isPending}
              canManage={direction === "outgoing"}
            />
          )}
          {shares.isError &&
          shares.data &&
          !(shares.error instanceof NetworkApiError && shares.error.status === 403) ? (
            <div role="alert" className="space-y-2">
              <p className="text-sm text-destructive">
                بارگذاری یا به‌روزرسانی اشتراک‌ها ناموفق بود.
              </p>
              <Button
                variant="outline"
                disabled={shares.isFetching}
                onClick={() => {
                  if (shares.isFetchNextPageError) void shares.fetchNextPage();
                  else void shares.refetch();
                }}
              >
                تلاش دوباره
              </Button>
            </div>
          ) : null}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function matchesSearch(share: Share, query: string) {
  return [share.property_id, share.note, share.target_agent]
    .filter(Boolean)
    .join(" ")
    .toLocaleLowerCase("fa-IR")
    .includes(query);
}

function SummaryCard({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-lg border bg-card/60 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums">
        {value === null ? "—" : toPersianDigits(String(value))}
      </p>
    </div>
  );
}

function ShareList({
  shares,
  loading,
  error,
  emptyTitle,
  emptyDescription,
  refetch,
  canLoadMore,
  loadingMore,
  onLoadMore,
  onRevoke,
  onExtend,
  mutationPending,
  canManage = false
}: {
  shares: Share[];
  loading: boolean;
  error: boolean;
  emptyTitle: string;
  emptyDescription: string;
  refetch: () => void;
  canLoadMore: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
  onRevoke: (share: Share) => void;
  onExtend: (share: Share) => void;
  mutationPending: boolean;
  canManage?: boolean;
}) {
  if (loading) return <ListSkeleton rows={4} />;
  if (error) return <ListError onRetry={refetch} />;

  return (
    <div className="space-y-3">
      {shares.length === 0 && <ListEmpty title={emptyTitle} description={emptyDescription} />}
      {shares.map((share) => (
        <ShareRow
          key={share.id}
          share={share}
          canManage={canManage}
          pending={mutationPending}
          onRevoke={() => onRevoke(share)}
          onExtend={() => onExtend(share)}
        />
      ))}
      {canLoadMore ? (
        <div className="flex justify-center pt-2">
          <Button variant="outline" disabled={loadingMore} onClick={onLoadMore}>
            {loadingMore
              ? "در حال بارگذاری…"
              : `بارگذاری ${toPersianDigits(String(PAGE_SIZE))} مورد بعدی`}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function ShareRow({
  share,
  canManage,
  onRevoke,
  onExtend,
  pending
}: {
  share: Share;
  canManage?: boolean;
  onRevoke?: () => void;
  onExtend?: () => void;
  pending?: boolean;
}) {
  const mode: ShareMode = share.mode;
  return (
    <Card>
      <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold" dir="auto">
              فایل {share.property_id.slice(0, 8)}…
            </span>
            <Badge variant="secondary">{SHARE_MODE_LABELS[mode] ?? mode}</Badge>
            <ShareStatusBadge status={share.status} />
          </div>
          <p className="text-xs text-muted-foreground">
            {share.target_agent ? `مسئول: ${share.target_agent} · ` : ""}
            ایجاد {formatJalali(share.created_at)}
            {share.expires_at ? ` · انقضا ${formatJalali(share.expires_at)}` : " · بدون انقضا"}
          </p>
          {share.note ? <p className="text-sm text-muted-foreground">«{share.note}»</p> : null}
          <p className="text-xs text-muted-foreground">
            مشخصات ملک و جزئیات اشتراک مجوزمند در API فعلی این فهرست ارائه نمی‌شود.
          </p>
          <div className="flex flex-wrap gap-1">
            <Badge variant="outline" className="gap-1 text-[10px]">
              <IconEyeOff className="h-3 w-3" /> شمارهٔ مالک در این فهرست نمایش داده نمی‌شود
            </Badge>
            <Badge variant="outline" className="gap-1 text-[10px]">
              <IconMapPin className="h-3 w-3" /> آدرس دقیق در این فهرست نمایش داده نمی‌شود
            </Badge>
          </div>
        </div>
        {canManage ? (
          <div className="flex shrink-0 items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={pending || !["ACTIVE", "EXPIRED"].includes(share.status)}
              onClick={onExtend}
            >
              <IconRefresh className="ml-1 h-3.5 w-3.5" /> تمدید ۳۰ روز
            </Button>
            <AlertDialog>
              <AlertDialogTrigger
                render={
                  <Button
                    size="sm"
                    variant="destructive"
                    disabled={pending || share.status !== "ACTIVE"}
                  />
                }
              >
                <IconTrash className="ml-1 h-3.5 w-3.5" /> لغو اشتراک
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>لغو اشتراک فایل؟</AlertDialogTitle>
                  <AlertDialogDescription>
                    دسترسی دفتر همکار پس از پاسخ موفق سرویس لغو می‌شود.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>انصراف</AlertDialogCancel>
                  <AlertDialogAction disabled={pending} onClick={onRevoke}>
                    لغو اشتراک
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
