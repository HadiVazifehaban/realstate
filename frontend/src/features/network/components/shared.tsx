"use client";

import * as React from "react";
import { IconInbox, IconAlertCircle } from "@tabler/icons-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AGENCY_STATUS_LABELS,
  COOPERATION_STATUS_LABELS,
  COMMISSION_STATUS_LABELS,
  DISPUTE_STATUS_LABELS,
  REFERRAL_STATUS_LABELS,
  SHARE_STATUS_LABELS,
  TRANSFER_STATUS_LABELS
} from "../types";

/** یک تاریخ میلادی را به شمسی خوانا تبدیل می‌کند؛ برای مقادیر خالی «—» برمی‌گرداند. */
export function formatJalali(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  try {
    return new Intl.DateTimeFormat("fa-IR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit"
    }).format(date);
  } catch {
    return date.toLocaleDateString("fa-IR");
  }
}

/** تاریخ و ساعت، برای لاگ‌ها و تایم‌لاین‌ها. */
export function formatJalaliDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  try {
    return new Intl.DateTimeFormat("fa-IR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    }).format(date);
  } catch {
    return date.toLocaleString("fa-IR");
  }
}

/** رنگ‌بج برای هر خانوادهٔ وضعیت، تا یک زبان بصری واحد در همهٔ صفحه‌های شبکه باشد. */
type BadgeTone = "default" | "secondary" | "destructive" | "outline";

const SHARE_TONES: Record<string, BadgeTone> = {
  ACTIVE: "default",
  EXPIRED: "secondary",
  REVOKED: "destructive",
  PENDING: "outline"
};

const COOPERATION_TONES: Record<string, BadgeTone> = {
  PENDING: "outline",
  APPROVED: "default",
  REJECTED: "destructive",
  COUNTER: "secondary",
  REVOKED: "destructive"
};

const COMMISSION_TONES: Record<string, BadgeTone> = {
  DRAFT: "outline",
  LOCKED: "secondary",
  PARTIALLY_PAID: "secondary",
  SETTLED: "default",
  DISPUTED: "destructive"
};

const DISPUTE_TONES: Record<string, BadgeTone> = {
  OPEN: "destructive",
  UNDER_REVIEW: "secondary",
  WAITING_RESPONSE: "outline",
  RESOLVED: "default",
  REJECTED: "secondary",
  ESCALATED: "destructive"
};

const REFERRAL_TONES: Record<string, BadgeTone> = {
  SENT: "outline",
  VIEWED: "secondary",
  ACCEPTED: "default",
  IN_FOLLOW_UP: "secondary",
  CONVERTED: "default",
  LOST: "destructive",
  CANCELLED: "secondary"
};

const TRANSFER_TONES: Record<string, BadgeTone> = {
  PENDING: "outline",
  COMPLETED: "default",
  REJECTED: "destructive",
  CANCELLED: "secondary"
};

export function ShareStatusBadge({ status }: { status: keyof typeof SHARE_STATUS_LABELS }) {
  return (
    <Badge variant={SHARE_TONES[status] ?? "outline"}>
      {SHARE_STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

export function CooperationStatusBadge({
  status
}: {
  status: keyof typeof COOPERATION_STATUS_LABELS;
}) {
  return (
    <Badge variant={COOPERATION_TONES[status] ?? "outline"}>
      {COOPERATION_STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

export function AgencyStatusBadge({ status }: { status: keyof typeof AGENCY_STATUS_LABELS }) {
  const tone: BadgeTone =
    status === "VERIFIED" ? "default" : status === "SUSPENDED" ? "destructive" : "outline";
  return <Badge variant={tone}>{AGENCY_STATUS_LABELS[status] ?? status}</Badge>;
}

export function CommissionStatusBadge({
  status
}: {
  status: keyof typeof COMMISSION_STATUS_LABELS;
}) {
  return (
    <Badge variant={COMMISSION_TONES[status] ?? "outline"}>
      {COMMISSION_STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

export function DisputeStatusBadge({ status }: { status: keyof typeof DISPUTE_STATUS_LABELS }) {
  return (
    <Badge variant={DISPUTE_TONES[status] ?? "outline"}>
      {DISPUTE_STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

export function ReferralStageBadge({ stage }: { stage: keyof typeof REFERRAL_STATUS_LABELS }) {
  return (
    <Badge variant={REFERRAL_TONES[stage] ?? "outline"}>
      {REFERRAL_STATUS_LABELS[stage] ?? stage}
    </Badge>
  );
}

export function TransferStatusBadge({ status }: { status: keyof typeof TRANSFER_STATUS_LABELS }) {
  return (
    <Badge variant={TRANSFER_TONES[status] ?? "outline"}>
      {TRANSFER_STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

// --------------------------------------------------------------------------- //
// List states: loading / error / empty — shared so every page looks the same.
// --------------------------------------------------------------------------- //

export function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-16 w-full rounded-lg" />
      ))}
    </div>
  );
}

export function ListError({ onRetry }: { onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-destructive/30 bg-destructive/5 px-5 py-12 text-center"
    >
      <IconAlertCircle className="size-8 text-destructive" aria-hidden="true" />
      <p className="text-sm text-muted-foreground">خطا در بارگذاری اطلاعات. لطفاً دوباره تلاش کنید.</p>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          تلاش مجدد
        </Button>
      ) : null}
    </div>
  );
}

export function ListEmpty({
  title,
  description,
  action
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border bg-muted/15 px-5 py-14 text-center">
      <span className="mb-1 flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
        <IconInbox className="size-7" aria-hidden="true" />
      </span>
      <p className="font-medium">{title}</p>
      {description ? (
        <p className="max-w-md text-sm leading-7 text-muted-foreground">{description}</p>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
