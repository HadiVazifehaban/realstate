import { NextRequest } from "next/server";
import { resolveAuthOrigin } from "./origin";

/** Normalize container-internal URLs without trusting Origin/Referer for routing. */
export function normalizeAuthRequest(request: NextRequest): NextRequest | null {
  try {
    const host = request.headers.get("host");
    if (!host || /[\s/@\\?#]/.test(host)) return null;
    const protocol = request.headers.get("x-forwarded-proto") ?? request.nextUrl.protocol.slice(0, -1);
    if (protocol !== "http" && protocol !== "https") return null;
    const url = new URL(request.url);
    const origin = `${protocol}://${host}`;
    const resolved = resolveAuthOrigin({ url: `${origin}${url.pathname}${url.search}`, headers: request.headers });
    if (!resolved.ok) return null;
    const browserOrigin = request.headers.get("origin");
    // POSTs from a different site must not select another allowlisted callback.
    if (browserOrigin && browserOrigin !== resolved.origin) return null;
    const headers = new Headers(request.headers);
    for (const name of [...headers.keys()]) {
      if (name.startsWith("x-forwarded-")) headers.delete(name);
    }
    headers.set("host", new URL(resolved.origin).host);
    headers.set("x-forwarded-host", new URL(resolved.origin).host);
    headers.set("x-forwarded-proto", protocol);
    return new NextRequest(`${resolved.origin}${url.pathname}${url.search}`, {
      method: request.method,
      headers,
      ...(request.method === "POST" ? { body: request.body, duplex: "half" as const } : {}),
      signal: request.signal
    });
  } catch {
    return null;
  }
}