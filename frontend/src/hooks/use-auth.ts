'use client';

/**
 * Identity for the dashboard, tolerant of three deployment shapes.
 *
 * 1. **Keycloak** (`NEXT_PUBLIC_KEYCLOAK_ISSUER` set) — the production posture.
 *    The session's access token is decoded to read realm roles, KYC status and
 *    the tenant id, exactly as the FastAPI core does server-side. The roles are
 *    used for *UI visibility only*; the API re-derives them from the signed
 *    token and is the actual enforcement point.
 * 2. **Clerk** — the starter's original provider, still supported for the
 *    managed dashboard demo.
 * 3. **Bypass** (`NEXT_PUBLIC_AUTH_BYPASS=true`) — a local-development escape
 *    hatch so screens unrelated to auth can be opened offline.
 *
 * Each mode gets its own hook and a constant flag picks between them, so the
 * rules of hooks hold. The bypass is a LOCAL convenience only: never enable it
 * where Clerk or Keycloak is the real gate.
 */
import * as React from 'react';
import { AUTH_BYPASS_ENABLED, KEYCLOAK_ENABLED } from '@/lib/utils';
import {
  type AuthJsSession,
  requestAuthJsSession,
  resetAuthJsSession
} from '@/lib/auth/session';
import { useClerk, useOrganization, useUser } from '@clerk/nextjs';
import { signOut as nextAuthSignOut } from 'next-auth/react';

export type SessionUser = {
  imageUrl?: string;
  fullName?: string | null;
  emailAddresses: Array<{ emailAddress: string }>;
  phoneNumber?: string;
};

/** Realm roles as Keycloak issues them. */
export const KEYCLOAK_ROLES = [
  'ROLE_ADMIN',
  'ROLE_SUPERVISOR',
  'ROLE_AGENCY_MANAGER',
  'ROLE_SENIOR_BROKER',
  'ROLE_JUNIOR_BROKER',
  // A private owner registering their own unit. Without it here the type would
  // reject the very role that makes `submitter_type === 'PERSON'` possible, so
  // the one path that distinguishes a شخص حقیقی from a بنگاه could not be
  // written against the typed list.
  'ROLE_OWNER',
  'ROLE_DATA_ANALYST',
  'ROLE_VERIFIED_USER',
  'ROLE_UNVERIFIED_USER'
] as const;
export type KeycloakRole = (typeof KEYCLOAK_ROLES)[number];

/** Mirrors `kyc_status` on the token; only VERIFIED clears the approval gate. */
export type KycStatus = 'PENDING' | 'VERIFIED' | 'REJECTED';

export interface AuthContext {
  user: SessionUser | null;
  roles: readonly string[];
  kycStatus: KycStatus;
  tenantId: string | null;
  saasTier: string | null;
  dailyPiiQuota: number | null;
  /** True only when the identity cleared the approval gate. */
  isApproved: boolean;
  /**
   * True while the realm session is still being fetched.
   *
   * Before the token arrives every claim reads as PENDING, so anything that
   * *decides* on `isApproved` must wait for this to clear — otherwise the
   * approval gate would bounce a verified user to /awaiting-approval on the
   * strength of a session it had not read yet.
   */
  isLoading: boolean;
}

const BYPASS_USER: SessionUser = {
  imageUrl: '',
  fullName: 'کاربر محلی',
  emailAddresses: [{ emailAddress: 'local@maskanchi.dev' }]
};

function useClerkUser(): SessionUser | null {
  const { user } = useUser();
  return user ?? null;
}

function useBypassUser(): SessionUser | null {
  return BYPASS_USER;
}

/**
 * Keycloak mode: the identity lives on the realm access token, not on a Clerk
 * user object. Reading the claims here keeps this independent of
 * `useAuthContext`, which dispatches back here.
 */
function useKeycloakUser(): SessionUser | null {
  const { claims } = useKeycloakClaims();
  return React.useMemo(() => contextFromClaims(claims).user, [claims]);
}

/** The signed-in user, or the local placeholder under the bypass. */
export function useAuthUser(): SessionUser | null {
  if (AUTH_BYPASS_ENABLED) return useBypassUser();
  if (KEYCLOAK_ENABLED) return useKeycloakUser();
  return useClerkUser();
}

function useClerkOrg() {
  const { organization } = useOrganization();
  return organization ?? null;
}

function useBypassOrg() {
  return null;
}

/**
 * The active organization, or `null` when no multi-tenant IdP is in play.
 *
 * Keycloak carries the tenant as a token claim, and the realm client is scoped
 * to one office, so there is no switchable organization list to expose here.
 */
function useKeycloakOrg() {
  return null;
}

/** The active organization, or `null` when no multi-tenant IdP is in play. */
export function useAuthOrganization() {
  if (AUTH_BYPASS_ENABLED) return useBypassOrg();
  if (KEYCLOAK_ENABLED) return useKeycloakOrg();
  return useClerkOrg();
}

function useClerkSignOut() {
  const { signOut } = useClerk();
  return signOut;
}

function useBypassSignOut() {
  // Nothing to sign out of locally; send the developer back to the root.
  return (_options?: { redirectUrl?: string }) => {
    if (typeof window !== 'undefined') {
      window.location.href = '/';
    }
  };
}

/**
 * Keycloak mode: clear this app's session cookie *and* end the realm SSO
 * session, so the next sign-in prompts for a password.
 *
 * Order matters. Auth.js `signOut` is awaited first — landing on Keycloak's
 * logout while the local cookie is still valid would let a fast back-navigation
 * resurrect a session the user just closed. The redirect is a full-page
 * `window.location` assignment rather than a client-side router push, on
 * purpose: the destination is another origin, and Next's router cannot cross it.
 */
function useKeycloakSignOut() {
  return async (options?: { redirectUrl?: string }) => {
    void options;
    resetAuthJsSession();
    try {
      const csrfResponse = await fetch('/api/auth/csrf', { cache: 'no-store' });
      if (!csrfResponse.ok) throw new Error('CSRF token unavailable');
      const { csrfToken } = (await csrfResponse.json()) as { csrfToken?: string };
      if (!csrfToken) throw new Error('CSRF token unavailable');
      const response = await fetch('/api/auth/keycloak-logout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ csrfToken }),
        cache: 'no-store',
        credentials: 'same-origin'
      });
      if (!response.ok) throw new Error('Sign-out failed');
      const result = (await response.json()) as { redirectUrl: string };
      // Clear the Auth.js session before leaving for Keycloak, so Back cannot
      // resurrect the signed-in app session. The logout endpoint needs only the
      // client id and registered post-logout redirect; it does not require an ID token.
      await nextAuthSignOut({ redirect: false });
      window.location.assign(result.redirectUrl);
    } catch {
      // Clear the local Auth.js cookie even if RP-initiated logout fails.
      try {
        await nextAuthSignOut({ redirect: false });
      } catch {
        // The sign-in page remains a safe fallback if Auth.js is unavailable.
      }
      window.location.assign('/auth/sign-in?logout=failed');
    }
  };
}

/**
 * `signOut`, accepting an optional redirect target.
 *
 * The returned shape differs by mode on purpose: only the Keycloak path awaits
 * anything, because only it has a second (cross-origin) hop to make. Callers
 * that just fire it can ignore the result.
 */
export function useAuthSignOut() {
  if (AUTH_BYPASS_ENABLED) return useBypassSignOut();
  if (KEYCLOAK_ENABLED) return useKeycloakSignOut();
  return useClerkSignOut();
}

const EMPTY_CONTEXT: AuthContext = {
  user: null,
  roles: [],
  kycStatus: 'PENDING',
  tenantId: null,
  saasTier: null,
  dailyPiiQuota: null,
  isApproved: false,
  isLoading: false
};

/** Build the context from decoded token claims. */
function contextFromClaims(claims: Record<string, unknown> | null): AuthContext {
  if (!claims) return EMPTY_CONTEXT;

  const realmAccess = claims.realm_access as { roles?: string[] } | undefined;
  // The realm's auto-assigned baseline role is not a grant, so it is dropped
  // here exactly as the API core drops it.
  const roles = (realmAccess?.roles ?? []).filter(
    (role) => !role.startsWith('default-roles')
  );
  const kycStatus = (claims.kyc_status as KycStatus | undefined) ?? 'PENDING';
  // The realm's attribute mapper emits this claim as a JSON *string* ("500"),
  // so a strict `typeof === 'number'` check dropped the quota everywhere it is
  // displayed. Parse the numeric form and leave anything else as unknown.
  const rawQuota = claims.daily_pii_quota;
  const explicitPhone = claims.phone_number ?? claims.phone ?? claims.mobile;
  const username = typeof claims.preferred_username === 'string' ? claims.preferred_username : '';
  const usernameDigits = username.replace(/[۰-۹٠-٩]/g, (digit) => {
    const code = digit.charCodeAt(0);
    return String(code >= 0x06f0 ? code - 0x06f0 : code - 0x0660);
  });
  const isIranianMobile = /^(?:\+?98|0098)?9\d{9}$|^09\d{9}$/.test(usernameDigits);
  const quota =
    typeof rawQuota === 'number'
      ? rawQuota
      : typeof rawQuota === 'string' && rawQuota.trim() !== '' && Number.isFinite(Number(rawQuota))
        ? Number(rawQuota)
        : null;

  return {
    user: {
      imageUrl: (claims.picture as string | undefined) ?? '',
      fullName: (claims.name as string | undefined) ?? null,
      emailAddresses: claims.email
        ? [{ emailAddress: claims.email as string }]
        : [{ emailAddress: (claims.preferred_username as string | undefined) ?? '' }],
      phoneNumber: typeof explicitPhone === 'string'
        ? explicitPhone
        : isIranianMobile
          ? usernameDigits
          : undefined
    },
    roles,
    kycStatus,
    tenantId: (claims.tenant_id as string | undefined) ?? null,
    saasTier: (claims.saas_tier as string | undefined) ?? null,
    dailyPiiQuota: quota,
    isApproved: kycStatus === 'VERIFIED',
    isLoading: false
  };
}

/**
 * The decoded realm claims, or null while no Auth.js session has arrived.
 *
 * `contextFromClaims` already turns claims into a complete `AuthContext`,
 * user included, so every Keycloak-mode reader derives from this one hook
 * rather than calling back into `useAuthUser` — that round trip would recurse.
 */
function useKeycloakClaims(): { claims: Record<string, unknown> | null; isLoading: boolean } {
  const { session, isLoading } = useAuthJsSession();
  const user = session?.user;
  const claims = React.useMemo(
    () => user ? {
      sub: user.id,
      name: user.name,
      email: user.email,
      picture: user.image,
      realm_access: { roles: user.roles ?? [] },
      kyc_status: user.kycStatus,
      tenant_id: user.tenantId,
      saas_tier: user.saasTier,
      daily_pii_quota: user.dailyPiiQuota,
      mobile_verified: user.mobileVerified,
      phone_number: user.phoneNumber
    } : null,
    [user]
  );
  return { claims, isLoading };
}

function useKeycloakContext(): AuthContext {
  const { claims, isLoading } = useKeycloakClaims();
  return React.useMemo(() => ({ ...contextFromClaims(claims), isLoading }), [claims, isLoading]);
}

/**
 * Read the Auth.js session when Keycloak is the provider.
 *
 * The request itself is shared module-wide (see `lib/auth/session`), so the
 * sidebar, this gate and the API clients all ride one round trip.
 *
 * Returns a null session in any other mode, which keeps this a no-op rather
 * than a missing-export crash for the Clerk/bypass builds.
 */
function useAuthJsSession(): { session: AuthJsSession | null; isLoading: boolean } {
  const [session, setSession] = React.useState<AuthJsSession | null>(null);
  const [isLoading, setIsLoading] = React.useState(KEYCLOAK_ENABLED);

  React.useEffect(() => {
    if (!KEYCLOAK_ENABLED) return;
    let cancelled = false;

    void requestAuthJsSession().then((result) => {
      if (cancelled) return;
      setSession(result);
      setIsLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  return { session, isLoading };
}

function useBypassContext(): AuthContext {
  return React.useMemo(
    () => ({ ...EMPTY_CONTEXT, user: BYPASS_USER, isApproved: true }),
    []
  );
}

function useClerkContextValue(): AuthContext {
  const user = useAuthUser();
  // A Clerk tenant session has no KYC concept, so treat a signed-in user as
  // approved and leave the approval gate to the Keycloak deployment.
  return React.useMemo(
    () => ({ ...EMPTY_CONTEXT, user, isApproved: !!user }),
    [user]
  );
}

/**
 * The full identity context for the active mode.
 *
 * Used by the nav filter and the approval gate. Roles here drive *visibility*
 * only — the API remains the enforcement point.
 */
export function useAuthContext(): AuthContext {
  if (AUTH_BYPASS_ENABLED) return useBypassContext();
  if (KEYCLOAK_ENABLED) return useKeycloakContext();
  return useClerkContextValue();
}

/** True when the caller cleared the approval gate. */
export function useIsApproved(): boolean {
  return useAuthContext().isApproved;
}

/** Realm roles for the active caller. */
export function useRealmRoles(): readonly string[] {
  return useAuthContext().roles;
}


