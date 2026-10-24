import 'server-only';

import { getServerAccessToken } from '@/lib/auth/server-token';

const API_ORIGIN = (process.env.API_SERVER_ORIGIN ?? 'http://backend:8080').replace(/\/$/, '');

/** Authenticated server-to-server FastAPI request; never expose its bearer token. */
export async function fetchPrivateApi(path: string, init: RequestInit = {}): Promise<Response> {
  if (!path.startsWith('/') || path.startsWith('//')) {
    throw new Error('API path must be a same-service absolute path');
  }
  const accessToken = await getServerAccessToken();
  if (!accessToken) throw new Error('Authentication required');

  const headers = new Headers(init.headers);
  headers.set('Authorization', `Bearer ${accessToken}`);
  headers.set('Cache-Control', 'no-store');
  return fetch(`${API_ORIGIN}/api/v1${path}`, {
    ...init,
    headers,
    cache: 'no-store',
    redirect: 'manual'
  });
}
