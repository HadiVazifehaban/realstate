"use client";

import * as React from 'react';
import { useAuthSignOut } from '@/hooks/use-auth';
import { KEYCLOAK_ENABLED, AUTH_BYPASS_ENABLED } from '@/lib/utils';
import { requestAuthJsSession } from '@/lib/auth/session';

/**
 * Signs the user out when the realm access token expires.
 *
 * Auth.js keeps its own session cookie for 8h, but the Keycloak access token
 * behind it is short-lived. Once the token dies every call to the FastAPI node
 * fails with 401, so leaving the user on the dashboard would just accumulate
 * failed requests with no way forward. This guard turns that into a clean
 * redirect to the sign-in page.
 *
 * The check is a polled deadline rather than one `setTimeout`: a background tab
 * has its timers throttled hard, so a timer armed for a 60s token may not fire
 * until the tab is restored. Comparing against the wall clock on each tick is
 * correct in both the foreground and the background.
 */
export function SessionExpiryGuard() {
  const signOut = useAuthSignOut();
  const enabled = KEYCLOAK_ENABLED && !AUTH_BYPASS_ENABLED;
  // `useAuthSignOut` returns a fresh closure on every render, so depending on it
  // directly would tear down and re-arm the interval on every render. Hold it in
  // a ref instead and read through a ref, keeping the effect mount-scoped.
  const signOutRef = React.useRef(signOut);
  signOutRef.current = signOut;

  React.useEffect(() => {
    if (!enabled) return;

    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | undefined;

    const signOutOnce = () => {
      if (cancelled) return;
      // Reuse the normal sign-out so the stale Auth.js cookie is cleared too;
      // a bare redirect would leave it in place and bounce straight back here.
      void signOutRef.current({ redirectUrl: "/auth/sign-in" });
    };

    const arm = (expSeconds: number) => {
      const msUntilExpiry = expSeconds * 1000 - Date.now();
      // Already expired (e.g. the tab was closed and reopened after the fact):
      // poll often so the redirect happens promptly rather than up to a full
      // interval later.
      const period = msUntilExpiry <= 0 ? 1_000 : Math.min(msUntilExpiry, 60_000);
      timer = setInterval(() => {
        if (Date.now() >= expSeconds * 1000) signOutOnce();
      }, period);
    };

    void requestAuthJsSession()
      .then((session) => {
        if (cancelled) return;
        const exp = session?.accessTokenExpiresAt;
        if (session?.authError || !exp || !Number.isFinite(exp) || exp <= Date.now() / 1000) {
          // A failed refresh or absent/expired expiry metadata means the server
          // no longer considers this Auth.js session usable.
          signOutOnce();
          return;
        }
        arm(exp);
      })
      .catch(() => {
        /* session fetch already swallows its own errors */
      });

    return () => {
      cancelled = true;
      if (timer !== undefined) clearInterval(timer);
    };
  }, [enabled]);

  return null;
}
