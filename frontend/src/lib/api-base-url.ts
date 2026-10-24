/**
 * Browser API traffic uses the authenticated same-origin BFF. Server-side
 * FastAPI calls must use the server-only `fetchPrivateApi` helper so bearer
 * credentials are never exposed to browser JavaScript.
 */
const API_ORIGIN = (process.env.API_SERVER_ORIGIN ?? 'http://backend:8080').replace(/\/$/, '');
const API_PATH = '/api/v1';
const BROWSER_PREFIX = '/backend';

export function apiBaseUrl(): string {
  return typeof window === 'undefined'
    ? `${API_ORIGIN}${API_PATH}`
    : `${BROWSER_PREFIX}${API_PATH}`;
}

export const apiProxyPrefix = BROWSER_PREFIX;

export function networkFailureMessage(error: unknown): string {
  const detail = error instanceof Error && error.message ? ` (${error.message})` : '';
  return `ارتباط با سرور داده برقرار نشد. آدرس سرویس در دسترس نیست${detail}.`;
}
