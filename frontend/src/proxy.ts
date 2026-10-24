import { clerkMiddleware } from '@clerk/nextjs/server';
import { NextRequest, NextResponse } from 'next/server';
import { AUTH_BYPASS_ENABLED, KEYCLOAK_ENABLED } from '@/lib/utils';
import { isApiPath, isPublicRoute } from '@/lib/auth/route-policy';
import { hasValidKeycloakSession, safeInternalPath } from '@/lib/auth/session-validity';

const withClerk = clerkMiddleware();

function privateResponseHeaders() {
  return {
    'Cache-Control': 'private, no-store, max-age=0',
    Vary: 'Cookie'
  };
}

/** Next.js 16 Proxy: default-deny for every dynamic page and API route. */
export default async function proxy(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const isPublic = isPublicRoute(pathname);
  const requestHeaders = new Headers(request.headers);

  // Never accept policy or return-path metadata supplied by the browser.
  requestHeaders.delete('x-shekarchi-public-route');
  requestHeaders.delete('x-shekarchi-protected-route');
  requestHeaders.delete('x-shekarchi-request-path');
  requestHeaders.set('x-shekarchi-public-route', isPublic ? 'true' : 'false');
  requestHeaders.set('x-shekarchi-protected-route', isPublic ? 'false' : 'true');
  requestHeaders.set(
    'x-shekarchi-request-path',
    `${request.nextUrl.pathname}${request.nextUrl.search}`
  );

  if (process.env.NODE_ENV === 'production' && !KEYCLOAK_ENABLED) {
    return NextResponse.json(
      { error: 'identity_provider_unavailable' },
      { status: 503, headers: privateResponseHeaders() }
    );
  }

  if (KEYCLOAK_ENABLED) {
    const { auth } = await import('@/lib/auth/config');
    const session = await auth();
    const validSession = hasValidKeycloakSession(session);

    if (!isPublic && !validSession) {
      if (isApiPath(pathname)) {
        return NextResponse.json(
          { detail: { error: 'authentication_required', message: 'برای ادامه وارد شوید.' } },
          {
            status: 401,
            headers: { ...privateResponseHeaders(), 'WWW-Authenticate': 'Bearer' }
          }
        );
      }

      const signInUrl = new URL('/auth/sign-in', request.url);
      const returnTo = safeInternalPath(`${pathname}${request.nextUrl.search}`);
      signInUrl.searchParams.set('callbackUrl', returnTo ?? '/');
      const response = NextResponse.redirect(signInUrl);
      for (const [name, value] of Object.entries(privateResponseHeaders())) {
        response.headers.set(name, value);
      }
      return response;
    }

    const response = NextResponse.next({ request: { headers: requestHeaders } });
    if (!isPublic) {
      for (const [name, value] of Object.entries(privateResponseHeaders())) {
        response.headers.set(name, value);
      }
    }
    return response;
  }

  if (AUTH_BYPASS_ENABLED) {
    return NextResponse.next({ request: { headers: requestHeaders } });
  }

  return withClerk(
    new NextRequest(request, { headers: requestHeaders }),
    {} as Parameters<typeof withClerk>[1]
  );
}

export const config = {
  matcher: [
    // Public static assets and Next internals do not contain private page data.
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|backend|trpc)(.*)'
  ]
};
