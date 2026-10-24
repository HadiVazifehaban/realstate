import { signIn } from "next-auth/react";

/**
 * Where the user lands when they did not ask for anything specific. Matches the
 * post-login default the middleware already uses.
 */
export const DEFAULT_SIGN_IN_CALLBACK = "/dashboard";

/**
 * Only same-origin paths are honoured. Auth.js would reject an absolute
 * callback anyway, but failing here keeps the user on the page instead of
 * bouncing them to an error screen.
 */
export function resolveCallbackUrl(search: string): string {
  const requested = new URLSearchParams(search).get("callbackUrl");
  return requested && requested.startsWith("/") && !requested.startsWith("//")
    ? requested
    : DEFAULT_SIGN_IN_CALLBACK;
}

/**
 * Hand the user to the Keycloak realm via Auth.js.
 *
 * `signIn('keycloak')` starts the authorization-code + PKCE flow against the
 * realm; on return Auth.js sets the session cookie and the callback URL is
 * resumed.
 *
 * `loginHint` is passed as the third `authorizationParams` argument.
 * `next-auth` appends it to the `/signin/keycloak` request, and `@auth/core`
 * merges the whole request query into the realm's authorization URL -- so
 * Keycloak receives `login_hint` and pre-fills its username field with the
 * identifier the user typed on our page.
 *
 * It is a pre-fill and nothing more. Credentials are deliberately not accepted
 * here: the realm owns the password, so a local password field would have
 * nowhere to send it, and a form that silently discards what the user typed is
 * worse than having no field at all.
 */
export async function beginKeycloakSignIn(options?: {
  callbackUrl?: string;
  loginHint?: string;
}): Promise<void> {
  const callbackUrl = options?.callbackUrl ?? DEFAULT_SIGN_IN_CALLBACK;
  const hint = options?.loginHint?.trim();

  await signIn("keycloak", { callbackUrl }, hint ? { login_hint: hint } : undefined);
}
