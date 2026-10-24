import { KEYCLOAK_ENABLED } from '@/lib/utils';

/**
 * Browser-side access to the Auth.js (next-auth v5) session.
 *
 * The browser receives display claims only. Tokens stay in the encrypted,
 * HttpOnly Auth.js cookie and are forwarded to FastAPI by server code.
 *
 * Both live in one module on purpose: the request is shared, so the sidebar,
 * the approval gate and every API client cost a single round trip rather than
 * one apiece.
 */

export interface AuthJsSession {
  accessTokenExpiresAt?: number;
  authError?: boolean;
  user?: {
    id?: string;
    name?: string | null;
    email?: string | null;
    image?: string | null;
    roles?: string[];
    kycStatus?: string;
    tenantId?: string;
    saasTier?: string;
    dailyPiiQuota?: number;
    mobileVerified?: boolean;
    phoneNumber?: string;
  };
}

let sessionRequest: Promise<AuthJsSession | null> | null = null;

/**
 * Fetch the Auth.js session once per page load.
 *
 * Returns null under Clerk/bypass, and null when there is no session, so
 * callers get a clean 'no token' answer instead of an exception.
 */
export function requestAuthJsSession(): Promise<AuthJsSession | null> {
  sessionRequest ??= (async () => {
    if (!KEYCLOAK_ENABLED) return null;
    try {
      const response = await fetch('/api/auth/session', { cache: 'no-store' });
      if (!response.ok) return null;
      const body = (await response.json()) as Record<string, unknown>;
      return {
        accessTokenExpiresAt:
          typeof body.accessTokenExpiresAt === 'number' ? body.accessTokenExpiresAt : undefined,
        authError: body.authError === true,
        user: body.user && typeof body.user === 'object'
          ? (body.user as AuthJsSession['user'])
          : undefined
      };
    } catch {
      // No session endpoint; the gate simply stays closed.
      return null;
    }
  })();
  return sessionRequest;
}

/**
 * Drop the cached session. Called on sign-out so a later sign-in in the same
 * tab reads the new token rather than the one just discarded.
 *
 * Also resets the city store's server-sync flag: the next login binds a new
 * subject and pulls that user's city, instead of showing the previous user's.
 */
export function resetAuthJsSession(): void {
  sessionRequest = null;
  try {
    // Dynamic import — session.ts must not hard-depend on the zustand store
    // (and `require` is unavailable in the Next.js ESM browser bundle).
    void import('@/store/useCityStore').then(({ useCityStore }) => {
      useCityStore.setState({ subject: null, hasSyncedServer: false });
    });
  } catch {
    // Store not loaded (SSR) — binder re-binds on next mount anyway.
  }
}

/**
 * Browser requests never carry API bearer credentials. They use the same-origin
 * BFF; only server-only API helpers may add Authorization.
 */
export async function authHeaders(): Promise<Record<string, string>> {
  return {};
}
