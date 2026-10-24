/**
 * Contracts for the office ("دفتر") page.
 *
 * Mirrors `app/schemas/license.py` — the node's own licence endpoint is what
 * tells the dashboard *which* office it is serving, how many seats the contract
 * allows and how long the offline grace window has left. Nothing here is
 * invented client-side: an unlicensed node must read as unlicensed.
 */

/** Every state `app/core/licensing.py` can report. */
export type LicenseStatus =
  | 'ACTIVE'
  | 'GRACE_PERIOD'
  | 'OFFLINE_GRACE_EXPIRED'
  | 'EXPIRED'
  | 'LOCKED_HARDWARE_MISMATCH'
  | 'NOT_INSTALLED'
  | 'INVALID_SIGNATURE';

export interface LicenseStatusResponse {
  status: string;
  is_usable: boolean;
  /** The node's own English diagnostic. Shown verbatim, never translated. */
  reason: string;
  node_mode: string;
  agency_name: string | null;
  license_id: string | null;
  max_concurrent_users: number | null;
  machine_fingerprint_hash: string | null;
  features: string[];
  issued_at: string | null;
  expires_at: string | null;
  last_heartbeat_at: string | null;
  offline_grace_deadline: string | null;
  grace_days: number;
}

export type StatusTone = 'ok' | 'warn' | 'bad';

interface StatusMeta {
  label: string;
  /** What the state means for the desk, in one line. */
  hint: string;
  tone: StatusTone;
}

const STATUS_META: Record<LicenseStatus, StatusMeta> = {
  ACTIVE: {
    label: 'پروانه فعال',
    hint: 'نود به‌تازگی با سرور پروانه همگام شده است.',
    tone: 'ok'
  },
  GRACE_PERIOD: {
    label: 'دورهٔ تنفس آفلاین',
    hint: 'نود هنوز با سرور پروانه تماس نگرفته؛ تا پایان مهلت، کارکرد کامل است.',
    tone: 'warn'
  },
  OFFLINE_GRACE_EXPIRED: {
    label: 'مهلت آفلاین تمام شده',
    hint: 'نود باید برای تمدید به شبکه وصل شود.',
    tone: 'bad'
  },
  EXPIRED: {
    label: 'پروانه منقضی شده',
    hint: 'اشتراک دفتر به پایان رسیده است.',
    tone: 'bad'
  },
  LOCKED_HARDWARE_MISMATCH: {
    label: 'قفل سخت‌افزاری ناهمخوان',
    hint: 'پروانه برای دستگاه دیگری صادر شده است.',
    tone: 'bad'
  },
  NOT_INSTALLED: {
    label: 'پروانه‌ای نصب نشده',
    hint: 'این نود بدون پروانهٔ تجاری اجرا می‌شود.',
    tone: 'bad'
  },
  INVALID_SIGNATURE: {
    label: 'امضای پروانه نامعتبر',
    hint: 'فایل پروانه دست‌کاری شده یا کلید عمومی عوض شده است.',
    tone: 'bad'
  }
};

/** Persian label and tone for a status the node reported, known or not. */
export function licenseStatusMeta(status: string): StatusMeta {
  return (
    STATUS_META[status as LicenseStatus] ?? {
      label: status || 'نامشخص',
      hint: 'وضعیت ناشناخته؛ گزارش نود را بررسی کنید.',
      tone: 'warn'
    }
  );
}

/** `NodeMode` is LOCAL for an office node, CLOUD_HUB for the hub itself. */
export const NODE_MODE_LABELS: Record<string, string> = {
  LOCAL: 'نود دفتر (محلی)',
  CLOUD_HUB: 'سرور مرکزی'
};

export function nodeModeLabel(mode: string): string {
  return NODE_MODE_LABELS[mode] ?? mode;
}
