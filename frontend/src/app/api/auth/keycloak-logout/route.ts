import { NextRequest, NextResponse } from "next/server";
import { handlers } from "@/lib/auth/config";
import { resolveAuthOrigin, sameOriginAuthRedirect } from "@/lib/auth/origin";

export const dynamic = "force-dynamic";

/** CSRF-check through Auth.js signout, then clear the local cookie and end SSO. */
export async function POST(request: NextRequest) {
  const resolvedOrigin = resolveAuthOrigin(request);
  if (!resolvedOrigin.ok) {
    return NextResponse.json(
      { error: "untrusted_request_origin" },
      { status: 400, headers: { "Cache-Control": "no-store" } }
    );
  }

  const form = await request.formData();
  const csrfToken = form.get("csrfToken");
  if (typeof csrfToken !== "string" || !csrfToken) {
    return NextResponse.json({ error: "csrf_validation_failed" }, { status: 400 });
  }

  const canonicalOrigin = process.env.AUTH_CANONICAL_URL
    ? new URL(process.env.AUTH_CANONICAL_URL).origin
    : resolvedOrigin.origin;
  const postLogoutRedirect = sameOriginAuthRedirect(canonicalOrigin as typeof resolvedOrigin.origin, "/auth/sign-in");
  if (!postLogoutRedirect) {
    return NextResponse.json(
      { error: "invalid_logout_redirect" },
      { status: 400, headers: { "Cache-Control": "no-store" } }
    );
  }
  const issuer = process.env.NEXT_PUBLIC_KEYCLOAK_ISSUER?.replace(/\/$/, "");

  let redirectUrl = postLogoutRedirect;
  if (issuer) {
    const logoutUrl = new URL(`${issuer}/protocol/openid-connect/logout`);
    logoutUrl.searchParams.set("client_id", process.env.KEYCLOAK_CLIENT_ID ?? "shekarchi-frontend");
    logoutUrl.searchParams.set("post_logout_redirect_uri", postLogoutRedirect);
    redirectUrl = logoutUrl.toString();
  }

  // Delegate CSRF verification and cookie invalidation to Auth.js itself.
  const authHeaders = new Headers(request.headers);
  authHeaders.set("content-type", "application/x-www-form-urlencoded");
  const authRequest = new NextRequest(new URL("/api/auth/signout", resolvedOrigin.origin), {
    method: "POST",
    headers: authHeaders,
    body: new URLSearchParams({ csrfToken, callbackUrl: postLogoutRedirect })
  });
  const signedOut = await handlers.POST(authRequest);
  if (signedOut.status >= 400) return signedOut;

  const response = NextResponse.json(
    { redirectUrl },
    { headers: { "Cache-Control": "private, no-store, max-age=0" } }
  );
  for (const cookie of signedOut.headers.getSetCookie()) {
    response.headers.append("Set-Cookie", cookie);
  }
  return response;
}
