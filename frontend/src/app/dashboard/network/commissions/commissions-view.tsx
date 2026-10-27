"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  IconLock,
  IconReceipt,
  IconWallet,
  IconCheck,
  IconSearch,
  IconChevronLeft,
  IconRefresh,
  IconShieldCheck
} from "@tabler/icons-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { NetworkToolbar } from "@/features/network/components/network-page";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
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
import { useCommission, useCommissions, useLockCommission } from "@/features/network/hooks";
import {
  CommissionStatusBadge,
  formatJalali,
  ListEmpty,
  ListError,
  ListSkeleton
} from "@/features/network/components/shared";
import { COMMISSION_STATUS_LABELS, type CommissionAgreement } from "@/features/network/types";

/** Keep the stored unit: never convert or sum different currencies. */
export function formatCommissionAmount(value: number, currency: string): string {
  const unit =
    { IRR: "ریال", IRT: "تومان", TOMAN: "تومان", USD: "دلار", EUR: "یورو" }[
      currency.toUpperCase()
    ] ?? currency;
  return `${value.toLocaleString("fa-IR")} ${unit}`;
}

/**
 * دفتر کمیسیون — به `/network/commissions` متصل است.
 * سرجمع، جدول سهم‌ها و پرداخت‌ها و قفل کردن توافق.
 */
export function CommissionsView() {
  const auth = useAuthContext();
  const agencyId = auth.tenantId;
  const queryClient = useQueryClient();

  const commissions = useCommissions({ agencyId });
  const [openId, setOpenId] = React.useState<string | null>(null);
  const [query, setQuery] = React.useState("");
  const [status, setStatus] = React.useState("ALL");
  const [model, setModel] = React.useState("ALL");

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["network", "commissions"] });
  };

  if (!agencyId) {
    return (
      <ListEmpty
        title="دفتر شما شناسایی نشد"
        description="برای دیدن دفتر کمیسیون، باید با حساب دفتر وارد شده باشید."
      />
    );
  }

  if (commissions.isPending) return <ListSkeleton rows={5} />;
  if (commissions.isError) return <ListError onRetry={() => void commissions.refetch()} />;

  const rows = commissions.data ?? [];
  const totals = new Map<string, number>();
  rows.forEach((row) =>
    totals.set(row.currency, (totals.get(row.currency) ?? 0) + row.basis_amount)
  );
  const filtered = rows.filter(
    (row) =>
      (status === "ALL" || row.status === status) &&
      (model === "ALL" || row.model === model) &&
      [row.id, row.property_id, row.note, row.source_agency_id, row.target_agency_id]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("fa-IR")
        .includes(query.trim().toLocaleLowerCase("fa-IR"))
  );

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <SummaryCard
          icon={<IconReceipt className="size-5" />}
          label="توافق‌های بارگذاری‌شده"
          value={rows.length.toLocaleString("fa-IR")}
        />
        <SummaryCard
          icon={<IconWallet className="size-5" />}
          label="مجموع مبلغ پایه به تفکیک ارز"
          value={
            totals.size
              ? [...totals]
                  .map(([currency, amount]) => formatCommissionAmount(amount, currency))
                  .join(" / ")
              : "—"
          }
        />
        <SummaryCard
          icon={<IconCheck className="size-5" />}
          label="تسویه‌شده"
          value={rows.filter((row) => row.status === "SETTLED").length.toLocaleString("fa-IR")}
        />
        <SummaryCard
          icon={<IconShieldCheck className="size-5" />}
          label="مورد اختلاف"
          value={rows.filter((row) => row.status === "DISPUTED").length.toLocaleString("fa-IR")}
        />
      </div>
      <p className="text-xs leading-6 text-muted-foreground">
        آمار مربوط به توافق‌های بارگذاری‌شده است. مبلغ پایه، ماندهٔ قابل پرداخت نیست؛ پرداخت‌ها و مانده
        در جزئیات هر توافق نمایش داده می‌شوند.
      </p>
      <NetworkToolbar>
        <div className="relative min-w-0 flex-1">
          <IconSearch
            className="absolute right-3 top-3 size-4 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            className="pr-9"
            aria-label="جستجوی توافق‌های کمیسیون"
            placeholder="جستجوی شناسه توافق، فایل، دفتر یا یادداشت…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <Select value={status} onValueChange={(value) => setStatus(value ?? "ALL")}>
          <SelectTrigger className="w-full sm:w-44" aria-label="فیلتر وضعیت کمیسیون">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">همه وضعیت‌ها</SelectItem>
            {Object.entries(COMMISSION_STATUS_LABELS).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={model} onValueChange={(value) => setModel(value ?? "ALL")}>
          <SelectTrigger className="w-full sm:w-36" aria-label="فیلتر مدل توافق">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">همه مدل‌ها</SelectItem>
            <SelectItem value="PERCENTAGE">درصدی</SelectItem>
            <SelectItem value="FIXED">مبلغ ثابت</SelectItem>
          </SelectContent>
        </Select>
        <Button
          variant="outline"
          disabled={commissions.isFetching}
          onClick={() => void commissions.refetch()}
        >
          <IconRefresh className="size-4" aria-hidden="true" /> به‌روزرسانی
        </Button>
      </NetworkToolbar>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold">دفتر توافق‌های مالی</h2>
        <span role="status" className="text-xs text-muted-foreground">
          {filtered.length.toLocaleString("fa-IR")} توافق از {rows.length.toLocaleString("fa-IR")}{" "}
          مورد بارگذاری‌شده
        </span>
      </div>

      {rows.length === 0 ? (
        <ListEmpty
          title="توافق کمیسیونی ثبت نشده"
          description="هنگام معاملهٔ مشترک بین دو دفتر، توافق کمیسیون اینجا ساخته می‌شود."
        />
      ) : filtered.length === 0 ? (
        <ListEmpty
          title="توافقی مطابق فیلترها پیدا نشد"
          description="عبارت جستجو یا فیلترها را تغییر دهید."
          action={
            <Button
              variant="outline"
              onClick={() => {
                setQuery("");
                setStatus("ALL");
                setModel("ALL");
              }}
            >
              پاک کردن فیلترها
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {filtered.map((r) => (
            <CommissionRow key={r.id} r={r} onOpen={() => setOpenId(r.id)} />
          ))}
        </div>
      )}

      <CommissionDetailDialog
        agreementId={openId}
        onOpenChange={(v) => !v && setOpenId(null)}
        onLocked={invalidate}
      />
    </div>
  );
}

function SummaryCard({
  icon,
  label,
  value
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <Card>
      <CardContent className="flex flex-col items-start gap-3 py-4 sm:flex-row">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          {icon}
        </span>
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="mt-2 break-words text-lg font-semibold tabular-nums">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function CommissionRow({ r, onOpen }: { r: CommissionAgreement; onOpen: () => void }) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium" dir="auto">
              {r.property_id ? `ملک ${r.property_id.slice(0, 8)}…` : "توافق بدون ملک"}
            </span>
            <Badge variant="secondary">{r.model === "PERCENTAGE" ? "درصدی" : "مبلغ ثابت"}</Badge>
            <CommissionStatusBadge status={r.status} />
          </div>
          <p className="text-xs text-muted-foreground">
            توافق <bdi>{r.id.slice(0, 8)}</bdi> · ایجاد {formatJalali(r.created_at)}
            {r.locked_at ? ` · قفل‌شده ${formatJalali(r.locked_at)}` : ""}
          </p>
          <p className="text-xs text-muted-foreground">
            دفتر مبدأ <bdi>{r.source_agency_id.slice(0, 8)}</bdi> · دفتر مقصد{" "}
            <bdi>{r.target_agency_id.slice(0, 8)}</bdi>
          </p>
          {r.note && (
            <p className="line-clamp-2 text-sm text-muted-foreground" dir="auto">
              {r.note}
            </p>
          )}
        </div>
        <div className="shrink-0 rounded-xl bg-muted/40 px-4 py-3 sm:text-left">
          <p className="mb-1 text-xs text-muted-foreground">مبلغ پایه توافق</p>
          <p className="font-semibold tabular-nums">
            {formatCommissionAmount(r.basis_amount, r.currency)}
          </p>
        </div>
        <Button size="sm" variant="outline" className="w-full shrink-0 sm:w-auto" onClick={onOpen}>
          جزئیات سهم‌ها و پرداخت‌ها
          <IconChevronLeft className="size-4" aria-hidden="true" />
        </Button>
      </CardContent>
    </Card>
  );
}

function CommissionDetailDialog({
  agreementId,
  onOpenChange,
  onLocked
}: {
  agreementId: string | null;
  onOpenChange: (open: boolean) => void;
  onLocked: () => void;
}) {
  const detail = useCommission(agreementId);
  const lock = useLockCommission();
  const d = detail.data;
  const canLock = d && d.status === "DRAFT";

  return (
    <Dialog open={!!agreementId} onOpenChange={onOpenChange}>
      <DialogContent
        dir="rtl"
        className="max-h-[85dvh] overflow-y-auto rounded-2xl p-5 sm:max-w-2xl sm:p-6"
      >
        <DialogHeader className="border-b pb-4 pl-6">
          <DialogTitle>جزئیات توافق کمیسیون</DialogTitle>
          <DialogDescription>سهم‌ها، پرداخت‌ها و ماندهٔ باقی‌مانده.</DialogDescription>
        </DialogHeader>
        {detail.isPending ? (
          <ListSkeleton rows={3} />
        ) : detail.isError || !d ? (
          <ListError onRetry={() => void detail.refetch()} />
        ) : (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <CommissionStatusBadge status={d.status} />
                <Badge variant="secondary">
                  {d.model === "PERCENTAGE" ? "توافق درصدی" : "مبلغ ثابت"}
                </Badge>
              </div>
              <span className="text-xs text-muted-foreground">
                ایجاد {formatJalali(d.created_at)}
              </span>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              {[
                { label: "مبلغ پایه", value: d.basis_amount },
                { label: "پرداخت‌شده", value: d.total_paid },
                { label: "باقی‌مانده", value: d.remaining }
              ].map((item) => (
                <div key={item.label} className="rounded-xl border bg-muted/30 p-4">
                  <p className="text-xs text-muted-foreground">{item.label}</p>
                  <p className="mt-2 font-semibold tabular-nums">
                    {formatCommissionAmount(item.value, d.currency)}
                  </p>
                </div>
              ))}
            </div>
            {d.note && (
              <p
                className="rounded-xl border border-dashed p-3 text-sm leading-7 text-muted-foreground"
                dir="auto"
              >
                {d.note}
              </p>
            )}

            <div>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
                <IconWallet className="size-4 text-primary" aria-hidden="true" /> سهم‌ها{" "}
                <Badge variant="secondary">{d.allocations.length.toLocaleString("fa-IR")}</Badge>
              </h3>
              {d.allocations.length === 0 ? (
                <p className="text-xs text-muted-foreground">سهمی ثبت نشده است.</p>
              ) : (
                <ul className="space-y-1">
                  {d.allocations.map((a) => (
                    <li
                      key={a.id}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border px-4 py-3 text-sm"
                    >
                      <span dir="auto">{a.agent || a.agency_id?.slice(0, 8) || "—"}</span>
                      <span className="text-muted-foreground">
                        {d.model === "PERCENTAGE"
                          ? `${a.percent.toLocaleString("fa-IR")}٪`
                          : formatCommissionAmount(a.fixed_amount, d.currency)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
                <IconReceipt className="size-4 text-primary" aria-hidden="true" /> تاریخچهٔ پرداخت‌ها{" "}
                <Badge variant="secondary">{d.payments.length.toLocaleString("fa-IR")}</Badge>
              </h3>
              {d.payments.length === 0 ? (
                <p className="text-xs text-muted-foreground">پرداختی ثبت نشده است.</p>
              ) : (
                <ul className="space-y-1">
                  {d.payments.map((p) => (
                    <li
                      key={p.id}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border px-4 py-3 text-sm"
                    >
                      <span dir="auto">
                        {p.reference || "بدون مرجع"} · {formatJalali(p.recorded_at)}
                      </span>
                      <span className="font-medium tabular-nums">
                        {formatCommissionAmount(p.amount, d.currency)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {canLock ? (
              <div className="flex flex-col gap-3 rounded-xl border bg-muted/20 p-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs leading-6 text-muted-foreground">
                  قفل‌کردن توافق، امکان تغییر سهم‌ها را محدود می‌کند.
                </p>
                <AlertDialog>
                  <AlertDialogTrigger render={<Button size="sm" disabled={lock.isPending} />}>
                    <IconLock className="ml-1 h-3.5 w-3.5" />
                    قفل کردن توافق
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>قفل کردن توافق کمیسیون؟</AlertDialogTitle>
                      <AlertDialogDescription>
                        پس از قفل، سهم‌ها دیگر قابل تغییر نیستند و برای ویرایش به تأیید مجدد نیاز
                        است.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>انصراف</AlertDialogCancel>
                      <AlertDialogAction
                        disabled={lock.isPending}
                        onClick={() =>
                          agreementId &&
                          !lock.isPending &&
                          lock.mutate({ agreementId }, { onSuccess: onLocked })
                        }
                      >
                        قفل کن
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            ) : null}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
