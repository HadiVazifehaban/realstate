import 'server-only';

import { cookies } from 'next/headers';
import { getToken } from 'next-auth/jwt';
import { getValidAuthSession } from '@/lib/auth/server-session';

/** Decrypt the token from Auth.js's HttpOnly cookie for server-to-server use. */
export async function getServerAccessToken(requestUrl?: string): Promise<string | null> {
  const session = await getValidAuthSession();
  if (!session) return null;

  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map(({ name, value }) => `${name}=${value}`)
    .join('; ');
  const secureCookie = cookieStore
    .getAll()
    .some(({ name }) => name.startsWith('__Secure-authjs.session-token'));
  const request = new Request(requestUrl ?? 'https://authjs-token.local', {
    headers: { cookie: cookieHeader }
  });
  const token = await getToken({
    req: request,
    secret: process.env.AUTH_SECRET ?? process.env.NEXTAUTH_SECRET,
    secureCookie
  });

  if (
    !token ||
    token.error === 'RefreshAccessTokenError' ||
    typeof token.accessToken !== 'string' ||
    typeof token.expiresAt !== 'number' ||
    token.expiresAt <= Math.floor(Date.now() / 1000)
  ) {
    return null;
  }
  return token.accessToken;
}
