import type { badgeVariants } from '@/components/ui/badge';
import type { VariantProps } from 'class-variance-authority';

type BadgeVariant = VariantProps<typeof badgeVariants>['variant'];
type BadgeProps = { variant?: BadgeVariant };

/**
 * Role ladder mirroring the backend's `UserRole` enum (app/models/enums.py).
 *
 * The backend orders the tiers from least to most privileged and gates
 * permissions off named sets (PII_READER_ROLES, LEAD_CLOSER_ROLES,
 * DATA_GOVERNOR_ROLES). Keep `value` byte-identical to the enum member so a
 * future `agency_user` API can send/receive these without a translation layer,
 * and keep the array in the same least->most privileged order.
 */
export type UserRole =
  | 'GUEST'
  | 'USER'
  | 'OWNER'
  | 'AGENT'
  | 'OFFICE_MANAGER'
  | 'SUPERVISOR'
  | 'ADMIN';

export type RoleMeta = {
  value: UserRole;
  label: string;
  description: string;
  badgeVariant: NonNullable<BadgeProps['variant']>;
  /** May read owner contact PII (backend PII_READER_ROLES). */
  canReadPii: boolean;
  /** May move a CRM lead to CLOSED_DEAL (backend LEAD_CLOSER_ROLES). */
  canCloseLead: boolean;
  /** May override valuation params or merge duplicates (DATA_GOVERNOR_ROLES). */
  isDataGovernor: boolean;
};

export const ROLES: RoleMeta[] = [
  {
    value: 'GUEST',
    label: 'بازدیدکننده',
    description: 'دسترسی عمومی به ویترین آگهی‌ها',
    badgeVariant: 'outline',
    canReadPii: false,
    canCloseLead: false,
    isDataGovernor: false
  },
  {
    value: 'USER',
    label: 'کاربر',
    description: 'کاربر احراز هویت‌شده',
    badgeVariant: 'secondary',
    canReadPii: false,
    canCloseLead: false,
    isDataGovernor: false
  },
  {
    value: 'OWNER',
    label: 'مالک',
    description: 'مالک ملک با ثبت مستقیم',
    badgeVariant: 'secondary',
    canReadPii: false,
    canCloseLead: false,
    isDataGovernor: false
  },
  {
    value: 'AGENT',
    label: 'مشاور',
    description: 'مشاور املاک',
    badgeVariant: 'default',
    canReadPii: true,
    canCloseLead: false,
    isDataGovernor: false
  },
  {
    value: 'OFFICE_MANAGER',
    label: 'مدیر دفتر',
    description: 'مدیر دفتر املاک',
    badgeVariant: 'default',
    canReadPii: true,
    canCloseLead: true,
    isDataGovernor: false
  },
  {
    value: 'SUPERVISOR',
    label: 'ناظر',
    description: 'ناظر کیفی و حقوقی',
    badgeVariant: 'secondary',
    canReadPii: true,
    canCloseLead: false,
    isDataGovernor: true
  },
  {
    value: 'ADMIN',
    label: 'مدیر سامانه',
    description: 'مدیر ارشد سامانه',
    badgeVariant: 'destructive',
    canReadPii: true,
    canCloseLead: true,
    isDataGovernor: true
  }
];

export const ROLE_VALUES: UserRole[] = ROLES.map((r) => r.value);

const ROLE_BY_VALUE = new Map(ROLES.map((r) => [r.value, r]));

export function getRoleMeta(role: string): RoleMeta {
  return (
    ROLE_BY_VALUE.get(role as UserRole) ?? {
      value: 'GUEST',
      label: role,
      description: 'نقش ناشناخته',
      badgeVariant: 'outline',
      canReadPii: false,
      canCloseLead: false,
      isDataGovernor: false
    }
  );
}

export function getRoleLabel(role: string): string {
  return getRoleMeta(role).label;
}

/** Options for the table's multi-select role filter. */
export const ROLE_OPTIONS = ROLES.map((r) => ({ value: r.value, label: r.label }));

// ---------------------------------------------------------------------------
// Account status
// ---------------------------------------------------------------------------

export const USER_STATUSES = ['ACTIVE', 'INACTIVE'] as const;
export type UserStatus = (typeof USER_STATUSES)[number];

type StatusMeta = {
  value: UserStatus;
  label: string;
  badgeVariant: NonNullable<BadgeProps['variant']>;
};

export const STATUS_META: Record<UserStatus, StatusMeta> = {
  ACTIVE: { value: 'ACTIVE', label: 'فعال', badgeVariant: 'default' },
  INACTIVE: { value: 'INACTIVE', label: 'غیرفعال', badgeVariant: 'secondary' }
};

export const STATUS_OPTIONS = USER_STATUSES.map((s) => ({
  value: s,
  label: STATUS_META[s].label
}));

export function getStatusLabel(status: string): string {
  return STATUS_META[status as UserStatus]?.label ?? status;
}
