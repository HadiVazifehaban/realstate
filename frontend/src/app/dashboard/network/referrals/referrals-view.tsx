"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { IconShare } from "@tabler/icons-react";

import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NetworkStats, NetworkToolbar } from "@/features/network/components/network-page";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";

import { useAuthContext } from "@/hooks/use-auth";
import { useReferrals, useUpdateReferralStage } from "@/features/network/hooks";
import {
  formatJalali,
  ListEmpty,
  ListError,
  ListSkeleton,
  ReferralStageBadge
} from "@/features/network/components/shared";
import {
  REFERRAL_STATUS_LABELS,
  type Referral,
  type ReferralStatus
} from "@/features/network/types";

const STAGE_ORDER: ReferralStatus[] = [
  "SENT",
  "VIEWED",
  "ACCEPTED",
  "IN_FOLLOW_UP",
  "CONVERTED",
  "LOST",
  "CANCELLED"
];

/**
 * ارجاع مشتری/سرنخ بین دفاتر — با تغییر مرحله.
 * به `/network/referrals` متصل است.
 */
export function ReferralsView() {
  const auth = useAuthContext();
  const agencyId = auth.tenantId;
  const queryClient = useQueryClient();

  const referrals = useReferrals({ agencyId });
  const updateStage = useUpdateReferralStage();
  const [query, setQuery] = React.useState("");
  const [stage, setStage] = React.useState("ALL");
  const items = referrals.data ?? [];
  const filtered = items.filter(
    (item) =>
      (stage === "ALL" || item.stage === stage) &&
      [item.subject, item.client_masked, item.assigned_to]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("fa-IR")
        .includes(query.trim().toLocaleLowerCase("fa-IR"))
  );

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["network", "referrals"] });
  };

  const onStage = (id: string, stage: ReferralStatus) => {
    updateStage.mutate({ referralId: id, payload: { stage } }, { onSuccess: invalidate });
  };

  if (!agencyId) {
    return (
      <ListEmpty
        title="دفتر شما شناسایی نشد"
        description="برای دیدن ارجاع‌ها، باید با حساب دفتر وارد شده باشید."
      />
    );
  }

  if (referrals.isPending) return <ListSkeleton rows={5} />;
  if (referrals.isError) return <ListError onRetry={() => void referrals.refetch()} />;

  return (
    <div className="space-y-3">
      <NetworkStats
        items={[
          { label: "ارجاع‌های بارگذاری‌شده", value: items.length },
          {
            label: "در انتظار بررسی",
            value: items.filter((item) => ["SENT", "VIEWED"].includes(item.stage)).length
          },
          {
            label: "در حال پیگیری",
            value: items.filter((item) => ["ACCEPTED", "IN_FOLLOW_UP"].includes(item.stage)).length
          },
          { label: "تبدیل‌شده", value: items.filter((item) => item.stage === "CONVERTED").length }
        ]}
      />
      <NetworkToolbar>
        <Input
          className="sm:max-w-sm"
          aria-label="جستجوی ارجاع‌ها"
          placeholder="جستجوی موضوع، مشتری یا مسئول…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <Select value={stage} onValueChange={(value) => setStage(value ?? "ALL")}>
          <SelectTrigger className="w-full sm:w-48" aria-label="فیلتر مرحله ارجاع">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">همه مراحل</SelectItem>
            {STAGE_ORDER.map((value) => (
              <SelectItem key={value} value={value}>
                {REFERRAL_STATUS_LABELS[value]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </NetworkToolbar>
      {!filtered.length && (
        <ListEmpty
          title={items.length ? "ارجاعی مطابق فیلترها پیدا نشد" : "ارجاعی ثبت نشده"}
          description="ارجاع مشتری به دفتر همکار و مسیر پیگیری آن در این بخش نمایش داده می‌شود."
        />
      )}
      {filtered.map((r) => (
        <ReferralRow key={r.id} r={r} onStage={onStage} pending={updateStage.isPending} />
      ))}
    </div>
  );
}

function ReferralRow({
  r,
  onStage,
  pending
}: {
  r: Referral;
  onStage: (id: string, stage: ReferralStatus) => void;
  pending: boolean;
}) {
  const nextStages = STAGE_ORDER;
  return (
    <Card>
      <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <IconShare className="h-4 w-4 text-primary" />
            <span className="font-medium" dir="auto">
              {r.subject}
            </span>
            <ReferralStageBadge stage={r.stage} />
          </div>
          <p className="text-xs text-muted-foreground" dir="auto">
            {r.client_masked ? `${r.client_masked} · ` : ""}
            {r.assigned_to ? `مسئول: ${r.assigned_to} · ` : ""}
            کارمزد {r.referral_fee_pct}٪ · {formatJalali(r.created_at)}
          </p>
          {r.outcome ? <p className="text-xs text-muted-foreground">نتیجه: «{r.outcome}»</p> : null}
        </div>
        <Select
          value={r.stage}
          onValueChange={(v) => v && onStage(r.id, v as ReferralStatus)}
          disabled={pending}
        >
          <SelectTrigger className="w-full sm:w-44" aria-label="تغییر مرحلهٔ ارجاع">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {nextStages.map((s) => (
              <SelectItem key={s} value={s}>
                {REFERRAL_STATUS_LABELS[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </CardContent>
    </Card>
  );
}
