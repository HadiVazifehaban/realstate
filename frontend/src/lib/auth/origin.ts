/**
 * Strict request-origin validation for Auth.js endpoints.
 *
 * Routing headers must agree with the allowlisted request origin. Client IP
 * metadata is ignored: Next.js adds it even for direct requests, and it must
 * never determine OAuth callback URLs.
 */
const DEFAULT_AUTH_ALLOWED_ORIGINS = [
  "http://localhost:3000",
  "http://127.0.0.1:3000",
  "http://192.168.31.168:3000",
  "https://shekkarchi.ir"
] as const;

export const AUTH_ALLOWED_ORIGINS: readonly string[] = DEFAULT_AUTH_ALLOWED_ORIGINS;

export type AuthAllowedOrigin = string;

export type OriginValidation =
  | { ok: true; origin: AuthAllowedOrigin }
  | { ok: false; reason: "static-auth-url" | "forwarded-header" | "invalid-origin" };

type AuthUrlEnvironment = {
  AUTH_URL?: string;
  NEXTAUTH_URL?: string;
  AUTH_ALLOWED_ORIGINS?: string;
};

const UNTRUSTED_ROUTING_HEADER_NAMES = new Set([
  "forwarded",
  "x-original-host",
  "x-original-url",
  "x-rewrite-url",
  "x-middleware-subrequest"
]);

/** Validate a direct or trusted-proxy-normalized request origin. */
export function resolveAuthOrigin(
  request: Pick<Request, "url" | "headers">,
  env: AuthUrlEnvironment = {
    AUTH_URL: process.env.AUTH_URL,
    NEXTAUTH_URL: process.env.NEXTAUTH_URL,
    AUTH_ALLOWED_ORIGINS: process.env.AUTH_ALLOWED_ORIGINS
  }
): OriginValidation {
  // NextAuth v5 replaces the request URL with this static origin when either
  // variable is present, which makes one instance serve only one callback host.
  if (env.AUTH_URL || env.NEXTAUTH_URL) {
    return { ok: false, reason: "static-auth-url" };
  }

  try {
    const requestUrl = new URL(request.url);
    const host = request.headers.get("host");
    if (!host || requestUrl.username || requestUrl.password) {
      return { ok: false, reason: "invalid-origin" };
    }

    const configuredOrigins = env.AUTH_ALLOWED_ORIGINS
      ?.split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    const allowedOrigins = configuredOrigins?.length
      ? configuredOrigins
      : [...DEFAULT_AUTH_ALLOWED_ORIGINS];
    const matched = allowedOrigins.find((candidate) => {
      try {
        const parsedCandidate = new URL(candidate);
        if (!["http:", "https:"].includes(parsedCandidate.protocol)) return false;
        if (parsedCandidate.username || parsedCandidate.password || parsedCandidate.pathname !== "/") return false;
      } catch {
        return false;
      }
      const allowed = new URL(candidate);
      return (
        requestUrl.origin === candidate &&
        requestUrl.protocol === allowed.protocol &&
        host.toLowerCase() === allowed.host.toLowerCase()
      );
    });

    if (!matched) return { ok: false, reason: "invalid-origin" };

    // Reject user-controlled routing metadata. Next.js itself may attach
    // x-forwarded-host/proto before invoking a route; those are accepted only
    // when they exactly agree with the already-allowlisted request origin.
    if ([...request.headers.keys()].some((name) => UNTRUSTED_ROUTING_HEADER_NAMES.has(name))) {
      return { ok: false, reason: "forwarded-header" };
    }
    const forwardedHost = request.headers.get("x-forwarded-host");
    const forwardedProto = request.headers.get("x-forwarded-proto");
    const forwardedPort = request.headers.get("x-forwarded-port");
    const allowed = new URL(matched);
    if (
      (forwardedHost && forwardedHost.toLowerCase() !== allowed.host.toLowerCase()) ||
      (forwardedProto && forwardedProto.toLowerCase().replace(/:$/, "") !== allowed.protocol.slice(0, -1)) ||
      (forwardedPort && forwardedPort !== (allowed.port || (allowed.protocol === "https:" ? "443" : "80")))
    ) {
      return { ok: false, reason: "forwarded-header" };
    }

    return { ok: true, origin: matched };
  } catch {
    return { ok: false, reason: "invalid-origin" };
  }
}

/** Build an internal redirect only after resolving the request Origin. */
export function sameOriginAuthRedirect(origin: string, path: string): string | null {
  if (!path.startsWith("/") || path.startsWith("//") || path.includes("\\")) return null;
  try {
    const target = new URL(path, origin);
    return target.origin === origin ? target.toString() : null;
  } catch {
    return null;
  }
}
