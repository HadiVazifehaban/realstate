/** Safe, non-secret Auth.js session metadata used by the server route guards. */
export interface GuardSession {
  user?: { id?: string | null } | null;
  accessTokenExpiresAt?: number;
  authError?: boolean;
}

export function hasValidKeycloakSession(
  session: GuardSession | null | undefined,
  nowSeconds = Math.floor(Date.now() / 1000)
): boolean {
  return Boolean(
    session?.user?.id &&
      !session.authError &&
      typeof session.accessTokenExpiresAt === 'number' &&
      Number.isFinite(session.accessTokenExpiresAt) &&
      session.accessTokenExpiresAt > nowSeconds
  );
}

/** Accept only same-origin absolute paths for post-auth redirects. */
export function safeInternalPath(value: string | null | undefined): string | null {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.includes('\\')) {
    return null;
  }
  if (/[\u0000-\u001f\u007f]/.test(value)) return null;

  try {
    const base = new URL('https://shekarchi.invalid');
    const target = new URL(value, base);
    if (target.origin !== base.origin) return null;
    return `${target.pathname}${target.search}${target.hash}`;
  } catch {
    return null;
  }
}
