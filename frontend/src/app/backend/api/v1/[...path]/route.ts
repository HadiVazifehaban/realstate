import { NextRequest, NextResponse } from 'next/server';
import { getServerAccessToken } from '@/lib/auth/server-token';
import { isPublicRoute } from '@/lib/auth/route-policy';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

type RouteContext = { params: Promise<{ path: string[] }> };
const ALLOWED_METHODS = new Set(['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']);
const API_ORIGIN = (process.env.API_SERVER_ORIGIN ?? 'http://backend:8080').replace(/\/$/, '');

async function proxyRequest(request: NextRequest, context: RouteContext): Promise<Response> {
  if (!ALLOWED_METHODS.has(request.method)) {
    return NextResponse.json({ detail: 'Method not allowed' }, { status: 405 });
  }

  const { path = [] } = await context.params;
  if (path.some((part) => part === '.' || part === '..' || part.includes('/') || part.includes('\\'))) {
    return NextResponse.json({ detail: 'Invalid API path' }, { status: 400 });
  }
  const backendPath = `/backend/api/v1/${path.map(encodeURIComponent).join('/')}`.replace(/\/$/, '');
  const publicRequest = isPublicRoute(backendPath);

  const headers = new Headers();
  for (const name of ['accept', 'content-type', 'if-match', 'if-none-match', 'range', 'idempotency-key', 'x-workspace-id']) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  if (!publicRequest) {
    const accessToken = await getServerAccessToken(request.url);
    if (!accessToken) {
      return NextResponse.json(
        { detail: { error: 'authentication_required', message: 'برای ادامه وارد شوید.' } },
        { status: 401, headers: { 'Cache-Control': 'private, no-store', 'WWW-Authenticate': 'Bearer' } }
      );
    }
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  const destination = new URL(
    `/api/v1/${path.map(encodeURIComponent).join('/')}${request.nextUrl.search}`,
    API_ORIGIN
  );
  let body: ArrayBuffer | undefined;
  if (!['GET', 'HEAD'].includes(request.method)) body = await request.arrayBuffer();

  let backendResponse: Response;
  try {
    backendResponse = await fetch(destination, {
      method: request.method,
      headers,
      body,
      cache: 'no-store',
      redirect: 'manual'
    });
  } catch {
    return NextResponse.json(
      { detail: { error: 'backend_unavailable', message: 'سرویس داده در دسترس نیست.' } },
      { status: 502, headers: { 'Cache-Control': 'private, no-store' } }
    );
  }

  const responseHeaders = new Headers();
  for (const name of ['content-type', 'content-disposition', 'accept-ranges', 'content-range']) {
    const value = backendResponse.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  responseHeaders.set('Cache-Control', 'private, no-store, max-age=0');
  responseHeaders.set('Vary', 'Cookie');
  const responseBody = [204, 304].includes(backendResponse.status)
    ? null
    : await backendResponse.arrayBuffer();
  return new NextResponse(responseBody, {
    status: backendResponse.status,
    headers: responseHeaders
  });
}

export const GET = proxyRequest;
export const HEAD = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
export const OPTIONS = proxyRequest;
