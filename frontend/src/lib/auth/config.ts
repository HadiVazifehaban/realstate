import NextAuth, { type NextAuthConfig } from 'next-auth';

/**
 * Auth.js (next-auth v5) configuration for the Keycloak realm.
 *
 * The realm access/refresh/ID tokens are stored only in Auth.js's encrypted,
 * HttpOnly JWT cookie. Browser sessions contain non-secret display claims;
 * Route Handlers decrypt the bearer credential and FastAPI verifies it again.
 *
 * The `shekarchi-frontend` realm client is a **public** client (PKCE), so no
 * client secret is used. The issuer must equal the API's `KEYCLOAK_ISSUER`
 * exactly — token verification pins it.
 *
 * We use the JWT strategy (no database): the session is a signed cookie, which
 * keeps the office node stateless and matches the offline-first deployment.
 *
 * Configure the public issuer per deployment. It must be reachable by the
 * browser and match the issuer used by the API to validate access tokens.
 */
function getProviders(): NextAuthConfig['providers'] {
  const providers: NextAuthConfig['providers'] = [];
  const publicIssuer = process.env.NEXT_PUBLIC_KEYCLOAK_ISSUER;

  if (publicIssuer) {
    const authUrl = `${publicIssuer}/protocol/openid-connect/auth`;
    const tokenUrl = `${publicIssuer}/protocol/openid-connect/token`;
    const userinfoUrl = `${publicIssuer}/protocol/openid-connect/userinfo`;
    const jwksUrl = `${publicIssuer}/protocol/openid-connect/certs`;
    const clientId = process.env.KEYCLOAK_CLIENT_ID ?? 'shekarchi-frontend';
    const clientSecret = process.env.KEYCLOAK_CLIENT_SECRET || undefined;

    // `shekarchi-frontend` is a public client, so PKCE + state is the whole
    // verification story; this is the stock Auth.js OIDC provider shape.
    providers.push({
      id: 'keycloak',
      name: 'Keycloak',
      type: 'oidc',
      issuer: publicIssuer,
      clientId,
      clientSecret,
      wellKnown: `${publicIssuer}/.well-known/openid-configuration`,
      authorization: {
        url: authUrl,
        params: { scope: 'openid profile email' },
      },
      token: tokenUrl,
      userinfo: userinfoUrl,
      jwks_endpoint: jwksUrl,
      // Endpoints are spelled out explicitly so the realm can be reached over plain
      // http in local dev, where `issuer` discovery is not always attempted first.
      checks: ['pkce', 'state'] as const,
      async profile(profile: Record<string, unknown>) {
        const p = profile as {
          sub: string;
          name?: string;
          preferred_username?: string;
          email?: string;
          picture?: string;
          realm_access?: { roles: string[] };
          kyc_status?: string;
          tenant_id?: string;
          agency_name?: string;
          daily_pii_quota?: number;
          mobile_verified?: boolean;
          phone_number?: string;
          phone?: string;
          mobile?: string;
        };
        return {
          id: p.sub,
          name: p.name ?? p.preferred_username,
          email: p.email,
          image: p.picture,
          roles: p.realm_access?.roles ?? [],
          kyc_status: p.kyc_status,
          tenant_id: p.tenant_id,
          agency_name: p.agency_name,
          daily_pii_quota: p.daily_pii_quota,
          mobile_verified: p.mobile_verified,
          phone_number: p.phone_number ?? p.phone ?? p.mobile,
        };
      },
      style: { logo: '/keycloak.svg', bg: '#fff', text: '#000' },
    } as any);
  }
  return providers;
}

export const authConfig: NextAuthConfig = {
  providers: getProviders(),
  // Auth.js derives callback URLs from the incoming request host so localhost,
  // LAN IPs, and a reverse-proxied VPS hostname can all work. trustHost is
  // required behind a proxy; in production, configure trusted proxy headers.
  trustHost: true,
  // Auth.js debug output can include provider error details. Keep it disabled
  // unless a developer explicitly opts in outside production.
  debug: process.env.NODE_ENV !== 'production' && process.env.AUTH_DEBUG === 'true',
  session: { strategy: 'jwt', maxAge: 60 * 60 * 8 },
  pages: {
    signIn: '/auth/sign-in',
    error: '/auth/sign-in'
  },
  callbacks: {
    /**
     * Persist the realm access token (and its expiry) on the JWT session.
     * `account.access_token` is only present on the initial sign-in exchange.
     */
    async jwt({ token, account, profile }) {
      if (account?.access_token) {
        token.accessToken = account.access_token;
        token.expiresAt =
          typeof account.expires_at === 'number'
            ? account.expires_at
            : readAccessTokenExpiry(account.access_token);
        // Kept for logout: Keycloak only skips its logout-confirmation screen
        // when the end-session request carries this as `id_token_hint`.
        token.idToken = account.id_token;
        // The refresh token is what lets the session outlive the access token's
        // short life. Keycloak issues it every time, so there is no reason to
        // drop it and re-authenticate instead.
        token.refreshToken = account.refresh_token;
        const claims = {
          ...((profile ?? {}) as Record<string, unknown>),
          ...readAccessTokenClaims(account.access_token)
        };
        const realmAccess = claims.realm_access as { roles?: unknown } | undefined;
        token.roles = Array.isArray(realmAccess?.roles)
          ? realmAccess.roles.filter((role): role is string => typeof role === 'string')
          : [];
        token.kycStatus = typeof claims.kyc_status === 'string' ? claims.kyc_status : 'PENDING';
        token.tenantId = typeof claims.tenant_id === 'string' ? claims.tenant_id : undefined;
        token.saasTier = typeof claims.saas_tier === 'string' ? claims.saas_tier : undefined;
        token.dailyPiiQuota = parseSafeNumber(claims.daily_pii_quota);
        token.mobileVerified = claims.mobile_verified === true;
        const phone = claims.phone_number ?? claims.phone ?? claims.mobile;
        const username = claims.preferred_username;
        token.phoneNumber =
          typeof phone === 'string'
            ? phone
            : typeof username === 'string' && isIranianMobile(username)
              ? username
              : undefined;
        token.displayName =
          typeof claims.name === 'string'
            ? claims.name
            : typeof claims.preferred_username === 'string'
              ? claims.preferred_username
              : undefined;
        token.emailAddress = typeof claims.email === 'string' ? claims.email : undefined;
        token.imageUrl = typeof claims.picture === 'string' ? claims.picture : undefined;
        token.error = undefined;
        return token as Record<string, unknown>;
      }
      // No new account exchange, so this is a later request against a session
      // cookie. That is where an expired access token would otherwise be
      // forwarded to FastAPI and rejected -- so rotate it first.
      return (await refreshAccessToken(token as Record<string, unknown>)) as typeof token;
    },
    /** Expose display/authorization hints only; credentials remain server-side. */
    session({ session, token }) {
      session.user = {
        ...session.user,
        id: typeof token.sub === 'string' ? token.sub : '',
        name: typeof token.displayName === 'string' ? token.displayName : session.user?.name,
        email: typeof token.emailAddress === 'string' ? token.emailAddress : session.user?.email,
        image: typeof token.imageUrl === 'string' ? token.imageUrl : session.user?.image,
        roles: Array.isArray(token.roles) ? token.roles : [],
        kycStatus: typeof token.kycStatus === 'string' ? token.kycStatus : 'PENDING',
        tenantId: typeof token.tenantId === 'string' ? token.tenantId : undefined,
        saasTier: typeof token.saasTier === 'string' ? token.saasTier : undefined,
        dailyPiiQuota: typeof token.dailyPiiQuota === 'number' ? token.dailyPiiQuota : undefined,
        mobileVerified: token.mobileVerified === true,
        phoneNumber: typeof token.phoneNumber === 'string' ? token.phoneNumber : undefined
      };
      session.accessTokenExpiresAt =
        typeof token.expiresAt === 'number' ? token.expiresAt : undefined;
      session.authError = token.error === 'RefreshAccessTokenError';
      return session;
    },
    /**
     * Redirect after successful sign-in
     */
    async redirect({ url, baseUrl }) {
      // Preserve safe same-origin destinations, including query strings; reject
      // protocol-relative and cross-origin callbacks to prevent open redirects.
      try {
        const base = new URL(baseUrl);
        const target = new URL(url, base);
        return target.origin === base.origin ? target.toString() : base.toString();
      } catch {
        return baseUrl;
      }
    }
  }
};

function isIranianMobile(value: string): boolean {
  const digits = value.replace(/[۰-۹٠-٩]/g, (digit) => {
    const code = digit.charCodeAt(0);
    return String(code >= 0x06f0 ? code - 0x06f0 : code - 0x0660);
  });
  return /^(?:\+?98|0098)?9\d{9}$|^09\d{9}$/.test(digits);
}

/**
 * Rotate the access token before it expires.
 *
 * The realm's `accessTokenLifespan` is 900 seconds -- 15 minutes -- while the
 * session cookie lives 8 hours. Without this, a user who stays logged in for a
 * quarter of an hour starts getting `401` on *every* call: the node verifies
 * the forwarded token against the realm's JWKS and rejects an expired one. The
 * symptom is 'listings stopped loading', and it looks like a bug in the query
 * rather than a clock, because the very same request works again the instant
 * the user signs back in.
 *
 * The wrapper runs on every `jwt()` pass, which Auth.js invokes per request
 * rather than only at sign-in, and hands back a token refreshed if it is close
 * to expiry. `skewSeconds` is the margin: refreshing at 90% of the lifetime
 * avoids presenting a credential that expires mid-flight.
 */
const SKEW_SECONDS = 60;

function readAccessTokenExpiry(accessToken: string): number | undefined {
  const claims = readAccessTokenClaims(accessToken);
  return typeof claims.exp === 'number' && Number.isFinite(claims.exp) ? claims.exp : undefined;
}

function readAccessTokenClaims(accessToken: string): Record<string, unknown> {
  try {
    const payload = accessToken.split('.')[1];
    if (!payload) return {};
    const decoded = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8')) as unknown;
    return decoded && typeof decoded === 'object' ? decoded as Record<string, unknown> : {};
  } catch {
    return {};
  }
}

function parseSafeNumber(value: unknown): number | undefined {
  const parsed = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : NaN;
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
}

async function refreshAccessToken(token: Record<string, unknown>): Promise<Record<string, unknown>> {
  const expiresAt = typeof token.expiresAt === 'number' ? token.expiresAt : 0;
  const nowInSeconds = Math.floor(Date.now() / 1000);

  // Still valid with the skew taken into account: nothing to do.
  if (expiresAt > nowInSeconds + SKEW_SECONDS) return token;

  const refreshToken = token.refreshToken;
  if (typeof refreshToken !== 'string' || !refreshToken) {
    return { ...token, error: 'RefreshAccessTokenError' as const };
  }

  const issuer = process.env.NEXT_PUBLIC_KEYCLOAK_ISSUER;
  if (!issuer) return { ...token, error: 'RefreshAccessTokenError' as const };

  try {
    const response = await fetch(`${issuer}/protocol/openid-connect/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'refresh_token',
        refresh_token: refreshToken,
        // A public client with PKCE: no secret to send, and the realm identifies
        // the client by this id alone.
        client_id: process.env.KEYCLOAK_CLIENT_ID ?? 'shekarchi-frontend'
      }),
      cache: 'no-store'
    });

    if (!response.ok) {
      // Keycloak once returned 400 with `invalid_grant` after the refresh token
      // itself expired, or a restart that invalidated every issued token. The
      // stale token is returned rather than a throw, so the *caller* signs in
      // deliberately instead of the request failing with a raw 500.
      return { ...token, error: 'RefreshAccessTokenError' as const };
    }

    const refreshed = (await response.json()) as {
      access_token?: string;
      id_token?: string;
      expires_in?: number;
      refresh_token?: string;
    };

    if (!refreshed.access_token) {
      return { ...token, error: 'RefreshAccessTokenError' as const };
    }

    return {
      ...token,
      accessToken: refreshed.access_token,
      // `expires_in` is seconds from now; Keycloak is the authority on its own
      // clock, so `expires_at` from the OAuth exchange is preferred when absent.
      expiresAt: refreshed.expires_in
        ? nowInSeconds + refreshed.expires_in
        : expiresAt,
      // A rotated refresh token is the norm, and using the old one afterwards
      // fails the next refresh, so it is replaced whenever one comes back.
      refreshToken: refreshed.refresh_token ?? refreshToken,
      // Keycloak issues a fresh ID token alongside the refresh; keep the
      // logout hint current so end-session never sees a stale one.
      idToken: refreshed.id_token ?? token.idToken,
      error: undefined
    };
  } catch {
    // Fail closed after the token expires. Retrying a stale access token would
    // allow a JWT session cookie to outlive the Keycloak credential.
    return { ...token, error: 'RefreshAccessTokenError' as const };
  }
}

/**
 * Canonical v5 entry point. `handlers` serves `/api/auth/*`, `auth()` is the
 * server-side session read, and `signIn`/`signOut` are the server actions the
 * UI and proxy call.
 */
export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);
