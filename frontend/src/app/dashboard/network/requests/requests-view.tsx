"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  IconBuilding,
  IconCheck,
  IconClock,
  IconPlus,
  IconScale,
  IconX
} from "@tabler/icons-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

import { useAuthContext } from "@/hooks/use-auth";
import { useDebounce } from "@/hooks/use-debounce";
import {
  useAgencies,
  useCooperations,
  useCreateCooperation,
  useDecideCooperation,
  networkKeys
} from "@/features/network/hooks";
import {
  CooperationStatusBadge,
  formatJalali,
  ListEmpty,
  ListError,
  ListSkeleton
} from "@/features/network/components/shared";
import {
  COOPERATION_SCOPE_LABELS,
  type Cooperation,
  type CooperationScope
} from "@/features/network/types";

/**
 * درخواست‌های همکاری — دریافتی و ارسالی، با تأیید/رد.
 * به `/network/cooperations?agency_id=…` متصل است.
 */
export function RequestsView() {
  const auth = useAuthContext();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const agencyId = auth.tenantId;
  const [direction, setDirection] = React.useState<"incoming" | "outgoing">(
    searchParams.get("direction") === "outgoing" ? "outgoing" : "incoming"
  );
  const [query, setQuery] = React.useState(searchParams.get("q") ?? "");
  const [status, setStatus] = React.useState(searchParams.get("status") ?? "ALL");
  const [scope, setScope] = React.useState(searchParams.get("scope") ?? "ALL");
  const [period, setPeriod] = React.useState(searchParams.get("period") ?? "ALL");
  const [offset, setOffset] = React.useState(0);
  const [loadedIncoming, setLoadedIncoming] = React.useState<Cooperation[]>([]);
  const [loadedOutgoing, setLoadedOutgoing] = React.useState<Cooperation[]>([]);
  const [loadedIncomingCount, setLoadedIncomingCount] = React.useState<number | null>(null);
  const [loadedOutgoingCount, setLoadedOutgoingCount] = React.useState<number | null>(null);
  const [seenIncomingPages, setSeenIncomingPages] = React.useState<number[]>([]);
  const [seenOutgoingPages, setSeenOutgoingPages] = React.useState<number[]>([]);
  const seenIncomingRef = React.useRef<number[]>([]);
  const seenOutgoingRef = React.useRef<number[]>([]);
  const debounceQuery = useDebounce(query, 300);
  const normalizedSearch = debounceQuery.trim().toLocaleLowerCase("fa-IR");
  const lastSearch = React.useRef(searchParams.toString());
  const requests = useCooperations(agencyId, {
    direction,
    status: status === "ALL" ? undefined : status,
    limit: 50,
    offset
  });
  const decide = useDecideCooperation();

  React.useEffect(() => {
    if (!requests.data) return;
    const update = direction === "incoming" ? setLoadedIncoming : setLoadedOutgoing;
    const setCount = direction === "incoming" ? setLoadedIncomingCount : setLoadedOutgoingCount;
    const setSeenPages = direction === "incoming" ? setSeenIncomingPages : setSeenOutgoingPages;
    const seenPages = direction === "incoming" ? seenIncomingRef : seenOutgoingRef;
    if (seenPages.current.includes(offset)) return;
    seenPages.current = [...seenPages.current, offset];
    setSeenPages((pages) => [...pages, offset]);
    update((current) => (offset === 0 ? requests.data! : appendUnique(current, requests.data!)));
    setCount((current) =>
      offset === 0 ? requests.data!.length : (current ?? 0) + requests.data!.length
    );
  }, [direction, offset, requests.data]);

  React.useEffect(() => {
    const current = searchParams.toString();
    if (current === lastSearch.current) return;
    lastSearch.current = current;
    const params = new URLSearchParams(current);
    setDirection(params.get("direction") === "outgoing" ? "outgoing" : "incoming");
    setQuery(params.get("q") ?? "");
    setStatus(params.get("status") ?? "ALL");
    setScope(params.get("scope") ?? "ALL");
    setPeriod(params.get("period") ?? "ALL");
    setOffset(0);
  }, [searchParams]);

  React.useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    if (direction === "outgoing") params.set("direction", direction);
    else params.delete("direction");
    if (debounceQuery) params.set("q", debounceQuery);
    else params.delete("q");
    if (status !== "ALL") params.set("status", status);
    else params.delete("status");
    if (scope !== "ALL") params.set("scope", scope);
    else params.delete("scope");
    if (period !== "ALL") params.set("period", period);
    else params.delete("period");
    const next = params.toString();
    if (next !== searchParams.toString()) {
      lastSearch.current = next;
      router.replace(next ? `?${next}` : "?", { scroll: false });
    }
  }, [debounceQuery, direction, period, router, scope, searchParams, status]);

  const invalidate = () => {
    if (agencyId)
      void queryClient.invalidateQueries({ queryKey: [...networkKeys.all(), "cooperations"] });
  };
  const onDecide = (id: string, decision: "approve" | "reject", reason?: string) => {
    if (!agencyId) return;
    decide.mutate(
      {
        cooperationId: id,
        decision,
        agencyId,
        payload: decision === "reject" ? { reason: reason ?? "" } : undefined
      },
      { onSuccess: invalidate }
    );
  };

  const filtered = React.useMemo(() => {
    const now = Date.now();
    const start =
      period === "TODAY"
        ? new Date(new Date().setHours(0, 0, 0, 0)).getTime()
        : period === "WEEK"
          ? now - 7 * 86400000
          : period === "MONTH"
            ? now - 30 * 86400000
            : null;
    const requestsForDirection = direction === "incoming" ? loadedIncoming : loadedOutgoing;
    return requestsForDirection.filter((item) => {
      const queryMatch =
        !normalizedSearch ||
        `${item.id} ${item.requester_agency_id} ${item.target_agency_id} ${item.requested_by}`
          .toLocaleLowerCase("fa-IR")
          .includes(normalizedSearch);
      return (
        queryMatch &&
        (scope === "ALL" || item.scope === scope) &&
        (start === null || new Date(item.created_at).getTime() >= start)
      );
    });
  }, [normalizedSearch, loadedIncoming, loadedOutgoing, direction, period, scope]);
  const actionRequired = loadedIncoming.filter((item) => item.status === "PENDING").length;
  const negotiations = [...loadedIncoming, ...loadedOutgoing].filter(
    (item) => item.status === "COUNTER"
  ).length;

  if (!agencyId)
    return (
      <ListEmpty
        title="دفتر شما شناسایی نشد"
        description="برای دیدن درخواست‌های همکاری، باید با حساب دفتر وارد شده باشید."
        action={
          <Button onClick={() => router.push("/dashboard/network/agencies")}>
            رفتن به دفاتر همکار
          </Button>
        }
      />
    );

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold">درخواست‌های همکاری</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            مدیریت درخواست‌های همکاری ملکی و اتصال دفاتر در شبکه شکارچی
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => router.push("/dashboard/network/agencies")}>
            شبکه دفاتر همکار
          </Button>
          <SendRequestDialog agencyId={agencyId} onSent={invalidate} />
        </div>
      </div>

      <section aria-label="نمای کلی درخواست‌ها" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          title="درخواست‌های نیازمند اقدام"
          value={loadedIncomingCount === null ? "…" : String(actionRequired)}
          description="درخواست‌های دریافتی بارگذاری‌شده؛ شمار کل در API موجود نیست"
          icon={<IconClock className="size-4" />}
        />
        <KpiCard
          title="در حال مذاکره"
          value={requests.isPending && offset === 0 ? "…" : String(negotiations)}
          description="از درخواست‌های بارگذاری‌شده؛ پیشنهاد متقابل به‌عنوان مذاکره"
          icon={<IconScale className="size-4" />}
        />
        <KpiCard
          title="همکاری‌های پذیرفته‌شده"
          value={
            requests.isPending
              ? "…"
              : String(
                  [...loadedIncoming, ...loadedOutgoing].filter(
                    (item) => item.status === "APPROVED"
                  ).length
                )
          }
          description="در میان درخواست‌های بارگذاری‌شده"
          icon={<IconCheck className="size-4" />}
        />
        <KpiCard
          title="درخواست‌های بارگذاری‌شده"
          value={requests.isPending ? "…" : String(loadedIncoming.length + loadedOutgoing.length)}
          description="مجموع موارد دریافتی و ارسالی بارگذاری‌شده"
          icon={<IconClock className="size-4" />}
        />
      </section>

      <div className="grid gap-3 rounded-2xl border bg-card p-4 sm:grid-cols-2 lg:grid-cols-4">
        <Input
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOffset(0);
          }}
          maxLength={100}
          placeholder="جستجو بر اساس شناسه درخواست یا دفتر…"
          aria-label="جستجوی درخواست‌ها"
        />
        <Select
          value={status}
          onValueChange={(value) => {
            setStatus(value ?? "ALL");
            setOffset(0);
          }}
        >
          <SelectTrigger aria-label="فیلتر وضعیت">
            <SelectValue placeholder="همه وضعیت‌ها" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">همه وضعیت‌ها</SelectItem>
            <SelectItem value="PENDING">در انتظار پاسخ</SelectItem>
            <SelectItem value="APPROVED">پذیرفته‌شده</SelectItem>
            <SelectItem value="COUNTER">پیشنهاد متقابل</SelectItem>
            <SelectItem value="REJECTED">ردشده</SelectItem>
            <SelectItem value="REVOKED">لغوشده</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={scope}
          onValueChange={(value) => {
            setScope(value ?? "ALL");
            setOffset(0);
          }}
        >
          <SelectTrigger aria-label="نوع همکاری">
            <SelectValue placeholder="همه انواع همکاری" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">همه انواع همکاری</SelectItem>
            {(Object.keys(COOPERATION_SCOPE_LABELS) as CooperationScope[]).map((value) => (
              <SelectItem key={value} value={value}>
                {COOPERATION_SCOPE_LABELS[value]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={period}
          onValueChange={(value) => {
            setPeriod(value ?? "ALL");
            setOffset(0);
          }}
        >
          <SelectTrigger aria-label="بازه زمانی">
            <SelectValue placeholder="همه زمان‌ها" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">همه زمان‌ها</SelectItem>
            <SelectItem value="TODAY">امروز</SelectItem>
            <SelectItem value="WEEK">۷ روز اخیر</SelectItem>
            <SelectItem value="MONTH">۳۰ روز اخیر</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Tabs
        value={direction}
        onValueChange={(value) => {
          if (value === "incoming" || value === "outgoing") {
            setDirection(value);
            setOffset(0);
          }
        }}
      >
        <TabsList>
          <TabsTrigger value="incoming">
            دریافتی (
            {loadedIncomingCount === null ? "…" : toPersianDigits(String(loadedIncomingCount))})
          </TabsTrigger>
          <TabsTrigger value="outgoing">
            ارسالی (
            {loadedOutgoingCount === null ? "…" : toPersianDigits(String(loadedOutgoingCount))})
          </TabsTrigger>
        </TabsList>
        <TabsContent value="incoming" className="mt-4">
          {renderRequestList(
            "incoming",
            direction,
            requests,
            loadedIncoming,
            filtered,
            onDecide,
            decide.isPending,
            offset,
            setOffset,
            seenIncomingPages
          )}
        </TabsContent>
        <TabsContent value="outgoing" className="mt-4">
          {renderRequestList(
            "outgoing",
            direction,
            requests,
            loadedOutgoing,
            filtered,
            onDecide,
            decide.isPending,
            offset,
            setOffset,
            seenOutgoingPages
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function appendUnique(current: Cooperation[], next: Cooperation[]): Cooperation[] {
  const seen = new Set(current.map((item) => item.id));
  return [...current, ...next.filter((item) => !seen.has(item.id))];
}

function renderRequestList(
  tab: "incoming" | "outgoing",
  direction: "incoming" | "outgoing",
  query: ReturnType<typeof useCooperations>,
  items: Cooperation[],
  filtered: Cooperation[],
  onDecide: (id: string, decision: "approve" | "reject", reason?: string) => void,
  pending: boolean,
  offset: number,
  setOffset: React.Dispatch<React.SetStateAction<number>>,
  seenPages: number[]
) {
  if (tab !== direction) return null;
  if (query.isPending && offset === 0 && items.length === 0) return <ListSkeleton rows={4} />;
  if (query.isError) return <ListError onRetry={() => void query.refetch()} />;
  if (items.length === 0)
    return (
      <ListEmpty
        title={tab === "incoming" ? "درخواست دریافتی ندارید" : "درخواست ارسالی ندارید"}
        description={
          tab === "incoming"
            ? "وقتی دفتری برای شما درخواست همکاری بفرستد، اینجا نمایش داده می‌شود."
            : "از فهرست دفاتر همکار، درخواست جدید بفرستید."
        }
      />
    );
  if (items.length > 0 && filtered.length === 0)
    return (
      <ListEmpty
        title="درخواستی مطابق فیلترها پیدا نشد"
        description="فیلترها را تغییر دهید تا موارد بیشتری نمایش داده شود."
      />
    );
  return (
    <div className="space-y-3">
      {filtered.map((item) => (
        <CooperationRow
          key={item.id}
          c={item}
          showActions={tab === "incoming"}
          onDecide={onDecide}
          pending={pending}
        />
      ))}
      {query.data && query.data.length >= 50 ? (
        <div className="flex justify-center pt-3">
          <Button
            variant="outline"
            disabled={query.isFetching}
            onClick={() => setOffset((value) => value + 50)}
          >
            بارگذاری درخواست‌های بعدی
          </Button>
        </div>
      ) : null}
      {offset > 0 && seenPages.includes(offset) && query.data?.length === 0 ? (
        <p className="text-center text-xs text-muted-foreground">
          درخواست دیگری برای بارگذاری نیست.
        </p>
      ) : null}
    </div>
  );
}

function CooperationRow({
  c,
  showActions,
  onDecide,
  pending
}: {
  c: Cooperation;
  showActions?: boolean;
  onDecide?: (id: string, d: "approve" | "reject", reason?: string) => void;
  pending?: boolean;
}) {
  const canDecide = showActions && c.status === "PENDING";
  const scopeLabel =
    (c.scope && COOPERATION_SCOPE_LABELS[c.scope as keyof typeof COOPERATION_SCOPE_LABELS]) ??
    c.scope ??
    "—";
  return (
    <Card>
      <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <IconBuilding className="h-4 w-4 text-primary" />
            <span className="font-medium" dir="auto">
              {scopeLabel}
            </span>
          </div>
          <p className="font-mono text-[11px] text-muted-foreground" dir="ltr">
            {formatRequestId(c.id)}
          </p>
          <p className="text-xs text-muted-foreground">
            {showActions ? "درخواست از دفتر" : "درخواست به دفتر"}:{" "}
            <span className="font-mono">
              {showActions ? c.requester_agency_id : c.target_agency_id}
            </span>
          </p>
          {c.default_commission_pct > 0 ? (
            <p className="text-xs text-muted-foreground">
              سهم پیشنهادی ثبت‌شده {toPersianDigits(String(c.default_commission_pct))}٪
            </p>
          ) : null}
          <p className="text-xs text-muted-foreground">ارسال‌شده در {formatJalali(c.created_at)}</p>
          <p className="text-xs text-muted-foreground">
            نوع داده: درخواست اتصال سازمانی دفترها؛ جزئیات ملک یا مشتری در API این درخواست موجود
            نیست.
          </p>
          {c.expires_at ? (
            <p className="text-xs text-muted-foreground">
              تا {formatJalali(c.expires_at)} معتبر است
            </p>
          ) : null}
          {c.decision_reason ? (
            <p className="text-xs text-muted-foreground">«{c.decision_reason}»</p>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          <CooperationStatusBadge status={c.status} />
          {canDecide && onDecide ? (
            <>
              <DecisionDialog
                decision="approve"
                cooperation={c}
                pending={pending}
                onConfirm={onDecide}
              />
              <DecisionDialog
                decision="reject"
                cooperation={c}
                pending={pending}
                onConfirm={onDecide}
              />
            </>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

function KpiCard({
  title,
  value,
  description,
  icon
}: {
  title: string;
  value: string;
  description: string;
  icon: React.ReactNode;
}) {
  return (
    <Card className="border-border/70 bg-card/70">
      <CardContent className="space-y-2 p-4">
        <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
          <span>{title}</span>
          <span className="text-primary">{icon}</span>
        </div>
        <p className="text-2xl font-semibold tabular-nums">
          {value === "—" ? value : toPersianDigits(value)}
        </p>
        <p className="text-xs leading-5 text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}

function DecisionDialog({
  decision,
  cooperation,
  pending,
  onConfirm
}: {
  decision: "approve" | "reject";
  cooperation: Cooperation;
  pending?: boolean;
  onConfirm: (id: string, decision: "approve" | "reject", reason?: string) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const [reason, setReason] = React.useState("");
  const approving = decision === "approve";
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button size="sm" variant={approving ? "outline" : "destructive"} disabled={pending} />
        }
      >
        {approving ? (
          <>
            <IconCheck className="ml-1 h-3.5 w-3.5" />
            پذیرش درخواست
          </>
        ) : (
          <>
            <IconX className="ml-1 h-3.5 w-3.5" />
            رد درخواست
          </>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{approving ? "پذیرش درخواست همکاری" : "رد درخواست همکاری"}</DialogTitle>
          <DialogDescription>
            {approving
              ? `درخواست «${COOPERATION_SCOPE_LABELS[cooperation.scope]}»${cooperation.default_commission_pct > 0 ? ` با سهم پیشنهادی ${cooperation.default_commission_pct}٪` : ""} را بررسی و در صورت تمایل تأیید کنید. این اقدام به‌تنهایی قرارداد حقوقی یا امضای دیجیتال نیست.`
              : "ثبت دلیل برای رد درخواست در سامانه الزامی است."}
          </DialogDescription>
        </DialogHeader>
        {!approving ? (
          <div className="space-y-2">
            <Label htmlFor={`reject-reason-${cooperation.id}`}>دلیل رد</Label>
            <Input
              id={`reject-reason-${cooperation.id}`}
              value={reason}
              maxLength={1000}
              onChange={(event) => setReason(event.target.value)}
              placeholder="دلیل را بنویسید"
            />
          </div>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            بازگشت
          </Button>
          <Button
            variant={approving ? "default" : "destructive"}
            disabled={pending || (!approving && !reason.trim())}
            onClick={() => {
              onConfirm(cooperation.id, decision, reason.trim());
              setOpen(false);
            }}
          >
            {approving ? "تأیید پذیرش" : "ثبت رد درخواست"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function formatRequestId(id: string): string {
  return `REQ-${id.replaceAll("-", "").slice(0, 8).toUpperCase()}`;
}

function toPersianDigits(value: string): string {
  return value.replace(/\d/g, (digit) => "۰۱۲۳۴۵۶۷۸۹"[Number(digit)]);
}

function SendRequestDialog({ agencyId, onSent }: { agencyId: string; onSent: () => void }) {
  const [open, setOpen] = React.useState(false);
  const [targetId, setTargetId] = React.useState("");
  const [scope, setScope] = React.useState<CooperationScope>("SHARE_LISTINGS");

  const agencies = useAgencies();
  const create = useCreateCooperation();

  const partners = (agencies.data ?? []).filter((a) => a && a.id !== agencyId);

  const submit = () => {
    if (!targetId) return;
    create.mutate(
      { requester_agency_id: agencyId, target_agency_id: targetId, scope, expires_in_days: 30 },
      {
        onSuccess: () => {
          setOpen(false);
          setTargetId("");
          onSent();
        }
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button />}>
        <IconPlus className="ml-1 h-4 w-4" />
        درخواست همکاری جدید
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>ارسال درخواست همکاری</DialogTitle>
          <DialogDescription>دفتر هدف و نوع همکاری را انتخاب کنید.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>دفتر هدف</Label>
            <Select value={targetId} onValueChange={(value) => setTargetId(value ?? "")}>
              <SelectTrigger>
                <SelectValue placeholder="انتخاب دفتر…" />
              </SelectTrigger>
              <SelectContent>
                {partners.map((a) => (
                  <SelectItem key={a.id} value={a.id}>
                    {a.name_fa || a.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>نوع همکاری</Label>
            <Select value={scope} onValueChange={(v) => setScope(v as CooperationScope)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(COOPERATION_SCOPE_LABELS) as CooperationScope[]).map((s) => (
                  <SelectItem key={s} value={s}>
                    {COOPERATION_SCOPE_LABELS[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            انصراف
          </Button>
          <Button onClick={submit} disabled={!targetId || create.isPending}>
            ارسال درخواست
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
