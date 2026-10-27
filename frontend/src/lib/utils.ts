import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Development-only escape hatch for the Clerk provider.
 *
 * The dashboard starter is wired end-to-end against Clerk (middleware, session
 * protection and `ClerkProvider` itself), which throws at render time when the
 * keys are absent. That blocks local UI work on screens that have nothing to do
 * with auth — e.g. the Maskanchi radar, which only talks to the LAN FastAPI node.
 *
 * Set `NEXT_PUBLIC_AUTH_BYPASS=true` to render without Clerk. The flag is
 * public and client-side, so it is a local-development convenience ONLY:
 * never enable it for a deployed or shared environment, and always leave the
 * real Clerk flow in place for production.
 */
export const AUTH_BYPASS_ENABLED =
  process.env.NODE_ENV !== 'production' && process.env.NEXT_PUBLIC_AUTH_BYPASS === 'true';

/** Placeholder session used only while the bypass is on. */
export const BYPASS_SESSION = {
  userId: 'dev_bypass_user',
  orgId: 'dev_bypass_org',
  orgRole: 'admin' as const
};

/**
 * True when the dashboard is wired to a Keycloak realm.
 *
 * Selecting the auth stack this way keeps every other component free of
 * conditionals: `use-auth` and `use-nav` each pick a mode-specific hook, and
 * the middleware branches once. The FastAPI core makes the matching decision
 * through `AUTH_MODE`.
 */
export const KEYCLOAK_ENABLED = Boolean(process.env.NEXT_PUBLIC_KEYCLOAK_ISSUER);

/** Realm + audience the dashboard expects; must match the API core's config. */
export const KEYCLOAK_ISSUER = process.env.NEXT_PUBLIC_KEYCLOAK_ISSUER ?? '';
export const KEYCLOAK_CLIENT_ID = process.env.KEYCLOAK_CLIENT_ID ?? 'shekarchi-frontend';

/**
 * True only when `<ClerkProvider />` is actually mounted.
 *
 * `providers.tsx` skips ClerkProvider under both the bypass and Keycloak, so
 * every component that reaches for a Clerk hook must gate on this flag rather
 * than on `!AUTH_BYPASS_ENABLED` — otherwise Clerk's hooks throw "can only be
 * used within the <ClerkProvider /> component" and the page 500s.
 */
export const CLERK_ENABLED = !AUTH_BYPASS_ENABLED && !KEYCLOAK_ENABLED;

/**
 * Formats a toman amount the way Iranian agents read it (e.g. 1.85 میلیارد).
 * Amounts stay as integers everywhere; only the display layer groups them.
 */
export function formatToman(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  if (value === 0) return '۰';

  if (value >= 1_000_000_000) {
    const billions = value / 1_000_000_000;
    return `${trimNumber(billions)} میلیارد تومان`;
  }
  if (value >= 1_000_000) {
    const millions = value / 1_000_000;
    return `${trimNumber(millions)} میلیون تومان`;
  }
  return `${toPersianDigits(value.toLocaleString('en-US'))} تومان`;
}

/** Per-square-meter price, which is how the valuation engine compares units. */
export function formatPricePerMeter(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${toPersianDigits(value.toLocaleString('en-US'))} تومان/متر`;
}

function trimNumber(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  return toPersianDigits(rounded.toLocaleString('en-US', { maximumFractionDigits: 1 }));
}

const PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

/** Converts ASCII digits in an already-formatted string to Persian digits. */
export function toPersianDigits(input: string): string {
  return input.replace(/\d/g, (digit) => PERSIAN_DIGITS[Number(digit)] as string);
}

export function formatBytes(
  bytes: number,
  opts: {
    decimals?: number;
    sizeType?: 'accurate' | 'normal';
  } = {}
) {
  const { decimals = 0, sizeType = 'normal' } = opts;

  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const accurateSizes = ['Bytes', 'KiB', 'MiB', 'GiB', 'TiB'];
  if (bytes === 0) return '0 Byte';
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(decimals)} ${
    sizeType === 'accurate' ? (accurateSizes[i] ?? 'Bytest') : (sizes[i] ?? 'Bytes')
  }`;
}
