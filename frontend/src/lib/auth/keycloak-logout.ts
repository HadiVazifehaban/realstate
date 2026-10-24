/**
 * Keycloak RP-initiated logout.
 *
 * Why this exists
 * ---------------
 * `signOut()` from Next-auth/Auth.js clears *this app's* session cookie and
 * nothing else. Keycloak holds its own SSO session in a separate cookie on its
 * own domain, so that cookie survives — and the next `signIn()` finds a live
 * SSO session and silently re-authenticates the same user. The result looks
 * like a broken sign-out: the UI returns to the sign-in page, but logging in
 * again asks for no password at all.
 *
 * Clearing the local cookie and then landing on Keycloak's end-session endpoint
 * kills the SSO session too, so the next sign-in genuinely prompts for
 * credentials. That is what the user means by 'خروج کامل'.
 *
 * Two values are sent:
 *
 * - `post_logout_redirect_uri` — where to come back to. Must be one of the
 *   client's registered redirect URIs, which is why it is built from
 *   `window.location.origin` rather than a hard-coded `localhost`: the app is
 *   opened by LAN IP on phones, and a hard-coded origin would 400 there.
 * - `id_token_hint` — sent whenever the session still holds the realm ID
 *   token. Without it Keycloak interposes its own "Do you want to log out?"
 *   confirmation screen (keycloak/keycloak discussion #12183): the SSO cookie
 *   survives until the user confirms, so one click would become two and an
 *   abandoned confirmation would leave the session alive. The hint is read
 *   from the session *before* the local cookie is discarded — a credential
 *   that is already being thrown away, not one trusted over the app's own.
 *   A session minted before the hint was persisted simply omits it and falls
 *   back to the confirmation screen.
 */

import { KEYCLOAK_ENABLED } from '@/lib/utils';

/** Realm issuer, e.g. `http://192.168.31.168:8082/realms/maskanchi`. */
function realmIssuer(): string | null {
  const issuer = process.env.NEXT_PUBLIC_KEYCLOAK_ISSUER;
  return issuer && issuer.length > 0 ? issuer.replace(/\/$/, '') : null;
}

/** Keycloak's end-session endpoint for the configured realm. */
export function keycloakLogoutUrl(
  postLogoutRedirectUri?: string,
  idTokenHint?: string | null
): string | null {
  if (!KEYCLOAK_ENABLED) return null;

  const issuer = realmIssuer();
  if (!issuer) return null;

  // Reach for the realm's own advertised endpoint rather than assembling the
  // path: it is documented in the OIDC discovery document and a realm mounted
  // at a different base would otherwise 404 silently.
  const url = new URL(`${issuer}/protocol/openid-connect/logout`);

  if (postLogoutRedirectUri) {
    url.searchParams.set('post_logout_redirect_uri', postLogoutRedirectUri);
    // Keycloak also accepts a `redirect_uri` alias; sending only the canonical
    // one keeps the URL from carrying the same intent twice.
    url.searchParams.set('client_id', process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID ?? 'maskanchi-frontend');
    // The hint is what makes Keycloak log out and redirect in one hop instead
    // of asking the user to confirm first; without it the SSO cookie outlives
    // this navigation.
    if (idTokenHint) {
      url.searchParams.set('id_token_hint', idTokenHint);
    }
  }

  return url.toString();
}

/**
 * The origin the browser actually loaded the app from. For server-side callers,
 * prefer the explicit deployment URL when configured, otherwise use localhost.
 */
export function currentOrigin(): string {
  if (typeof window !== 'undefined') return window.location.origin;
  return (process.env.AUTH_CANONICAL_URL ?? process.env.NEXTAUTH_URL ?? 'http://localhost:3000').replace(/\/$/, '');
}
