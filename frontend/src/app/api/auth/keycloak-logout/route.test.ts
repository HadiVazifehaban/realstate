// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const auth = vi.hoisted(() => ({ POST: vi.fn() }));
vi.mock("@/lib/auth/config", () => ({ handlers: auth }));
import { POST } from "./route";

describe("Keycloak logout landing redirect", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetAllMocks();
  });

  it("clears the local session and returns to localhost landing after SSO logout", async () => {
    vi.stubEnv("AUTH_URL", "");
    vi.stubEnv("NEXTAUTH_URL", "");
    vi.stubEnv("AUTH_CANONICAL_URL", "");
    vi.stubEnv("AUTH_ALLOWED_ORIGINS", "http://localhost:3000");
    vi.stubEnv("NEXT_PUBLIC_KEYCLOAK_ISSUER", "http://localhost:8082/realms/maskanchi");
    auth.POST.mockResolvedValue(new Response(null, {
      headers: { "Set-Cookie": "authjs.session-token=; Max-Age=0; Path=/; HttpOnly" }
    }));
    const response = await POST(new NextRequest("http://0.0.0.0:3000/api/auth/keycloak-logout", {
      method: "POST",
      headers: { host: "localhost:3000", origin: "http://localhost:3000", "x-forwarded-proto": "http" },
      body: new URLSearchParams({ csrfToken: "test-csrf" })
    }));
    expect(response.status).toBe(200);
    const { redirectUrl } = await response.json();
    const logout = new URL(redirectUrl);
    expect(logout.pathname).toBe("/realms/maskanchi/protocol/openid-connect/logout");
    expect(logout.searchParams.get("post_logout_redirect_uri")).toBe("http://localhost:3000/");
    expect(response.headers.get("set-cookie")).toContain("Max-Age=0");
    const delegated = auth.POST.mock.calls[0][0] as NextRequest;
    const form = await delegated.formData();
    expect(form.get("csrfToken")).toBe("test-csrf");
    expect(form.get("callbackUrl")).toBe("http://localhost:3000/");
  });

  it("rejects logout without a CSRF token", async () => {
    vi.stubEnv("AUTH_URL", "");
    vi.stubEnv("NEXTAUTH_URL", "");
    vi.stubEnv("AUTH_ALLOWED_ORIGINS", "http://localhost:3000");
    const response = await POST(new NextRequest("http://localhost:3000/api/auth/keycloak-logout", {
      method: "POST",
      headers: { host: "localhost:3000" },
      body: new URLSearchParams()
    }));
    expect(response.status).toBe(400);
    expect(auth.POST).not.toHaveBeenCalled();
  });

  it("rejects cross-origin logout even when the host is allowlisted", async () => {
    vi.stubEnv("AUTH_URL", "");
    vi.stubEnv("NEXTAUTH_URL", "");
    vi.stubEnv("AUTH_ALLOWED_ORIGINS", "http://localhost:3000");
    const response = await POST(new NextRequest("http://localhost:3000/api/auth/keycloak-logout", {
      method: "POST",
      headers: { host: "localhost:3000", origin: "https://attacker.example" },
      body: new URLSearchParams({ csrfToken: "test-csrf" })
    }));
    expect(response.status).toBe(400);
    expect(auth.POST).not.toHaveBeenCalled();
  });
});