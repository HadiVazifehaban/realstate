"use client";

import { useState } from "react";
import { IconArrowsExchange, IconArrowLeft } from "@tabler/icons-react";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { NetworkStats, NetworkToolbar } from "@/features/network/components/network-page";
import { TRANSFER_STATUS_LABELS } from "@/features/network/types";
import { useAuthContext } from "@/hooks/use-auth";
import { useTransfers } from "@/features/network/hooks";
import { TransferCreateDialog } from "./transfer-create-dialog";
import {
  formatJalali,
  ListEmpty,
  ListError,
  ListSkeleton,
  TransferStatusBadge
} from "@/features/network/components/shared";

/**
 * تاریخچهٔ انتقال فایل — به `/network/transfers` متصل است.
 * هر سطر مسئولیت فایل را از یک دفتر به دفتر دیگر نشان می‌دهد.
 */
export function TransfersView() {
  const auth = useAuthContext();
  const agencyId = auth.tenantId;
  const transfers = useTransfers({ agencyId });
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("ALL");
  const items = transfers.data ?? [];
  const filtered = items.filter(
    (item) =>
      (status === "ALL" || item.status === status) &&
      [item.property_id, item.from_user, item.to_user, item.reason]
        .join(" ")
        .toLocaleLowerCase("fa-IR")
        .includes(query.trim().toLocaleLowerCase("fa-IR"))
  );

  if (!agencyId) {
    return (
      <ListEmpty
        title="دفتر شما شناسایی نشد"
        description="برای دیدن تاریخچهٔ انتقال، باید با حساب دفتر وارد شده باشید."
      />
    );
  }

  if (transfers.isPending) return <ListSkeleton rows={5} />;
  if (transfers.isError) return <ListError onRetry={() => void transfers.refetch()} />;

  return (
    <div className="space-y-3">
      <NetworkStats
        items={[
          { label: "انتقال‌های بارگذاری‌شده", value: items.length },
          { label: "تکمیل‌شده", value: items.filter((item) => item.status === "COMPLETED").length },
          { label: "در انتظار", value: items.filter((item) => item.status === "PENDING").length },
          {
            label: "رد یا لغوشده",
            value: items.filter((item) => ["REJECTED", "CANCELLED"].includes(item.status)).length
          }
        ]}
      />
      <NetworkToolbar>
        <Input
          className="sm:max-w-xs"
          aria-label="جستجوی انتقال‌ها"
          placeholder="جستجوی کد فایل، مسئول یا دلیل انتقال…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <Select value={status} onValueChange={(value) => setStatus(value ?? "ALL")}>
          <SelectTrigger className="w-full sm:w-44" aria-label="فیلتر وضعیت انتقال">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">همه وضعیت‌ها</SelectItem>
            {Object.entries(TRANSFER_STATUS_LABELS).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <TransferCreateDialog agencyId={agencyId} />
      </NetworkToolbar>
      {!filtered.length && (
        <ListEmpty
          title={items.length ? "انتقالی مطابق فیلترها پیدا نشد" : "هنوز فایلی منتقل نشده"}
          description="با «ثبت انتقال فایل» مسئولیت یک فایل را با تأیید صریح به دفتر همکار واگذار کنید."
        />
      )}
      {filtered.map((t) => (
        <div key={t.id} className="rounded-2xl border border-border bg-card p-5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="mb-3 flex items-center gap-2 font-medium" dir="auto">
                <IconArrowsExchange className="size-5 text-primary" aria-hidden="true" />
                فایل {t.property_id.slice(0, 8)}…
              </p>
              <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <bdi>{t.from_user || "دفتر مبدأ"}</bdi>
                <IconArrowLeft className="size-3" aria-label="به" />
                <bdi>{t.to_user || "دفتر مقصد"}</bdi> · {formatJalali(t.created_at)}
              </p>
              {t.reason ? (
                <p className="mt-1 text-xs text-muted-foreground">دلیل: «{t.reason}»</p>
              ) : null}
              <p className="mt-1 text-xs text-muted-foreground">
                کارمزد باقی‌ماندهٔ دفتر قبل: {t.residual_commission_pct}٪
              </p>
            </div>
            <TransferStatusBadge status={t.status} />
          </div>
        </div>
      ))}
    </div>
  );
}
