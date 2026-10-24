// @vitest-environment node
import { describe, expect, it } from "vitest";
import { Auth, type AuthConfig } from "@auth/core";
import { createActionURL } from "@auth/core";
import { resolveAuthOrigin, sameOriginAuthRedirect } from "./origin";

function request(url: string, headers: Record<string, string> = {}) {
  const parsed = new URL(url);
  return new Request(url, {
    headers: { host: parsed.host, ...headers }
  });
}

describe("Auth.js origin policy", () => {
  it.each(["http://localhost:3000", "http://127.0.0.1:3000", "http://192.168.31.168:3000", "https://shekkarchi.ir"])(
    "accepts direct allowlisted origin %s",
    (origin) => {
      expect(resolveAuthOrigin(request(`${origin}/api/auth/providers`))).toEqual({
        ok: true,
        origin
      });
    }
  );

  it.each([
    ["https://attacker.example", "attacker host"],
    ["http://localhost:3001", "wrong port"],
    ["https://localhost:3000", "wrong protocol"],
    ["https://www.shekkarchi.ir", "www alias"],
    ["https://shekkarchi.ir:444", "wrong public port"]
  ])("rejects %s (%s)", (url) => {
    expect(resolveAuthOrigin(request(url)).ok).toBe(false);
  });

  it("rejects Host that disagrees with request URL", () => {
    expect(
      resolveAuthOrigin(
        new Request("http://localhost:3000/api/auth/providers", {
          headers: { host: "attacker.example" }
        })
      )
    ).toMatchObject({ ok: false, reason: "invalid-origin" });
  });

  it.each(["forwarded", "x-original-host", "x-middleware-subrequest"])(
    "fails closed on untrusted %s",
    (name) => {
      expect(
        resolveAuthOrigin(request("https://shekkarchi.ir/api/auth/providers", { [name]: "evil" }))
      ).toMatchObject({ ok: false, reason: "forwarded-header" });
    }
  );

  it("accepts matching framework-forwarded host/proto for an allowlisted localhost origin", () => {
    expect(
      resolveAuthOrigin(
        request("http://localhost:3000/api/auth/providers", {
          "x-forwarded-host": "localhost:3000",
          "x-forwarded-proto": "http"
        })
      )
    ).toEqual({ ok: true, origin: "http://localhost:3000" });
  });

  it("rejects forwarded host/proto that disagree with the allowlisted request origin", () => {
    expect(
      resolveAuthOrigin(
        request("http://localhost:3000/api/auth/providers", {
          "x-forwarded-host": "attacker.example",
          "x-forwarded-proto": "https"
        })
      )
    ).toMatchObject({ ok: false, reason: "forwarded-header" });
  });

  it("rejects static Auth.js URLs because they pin a single callback origin", () => {
    const allowedRequest = request("http://localhost:3000/api/auth/providers");
    expect(resolveAuthOrigin(allowedRequest, { AUTH_URL: "https://shekkarchi.ir" })).toMatchObject({
      ok: false,
      reason: "static-auth-url"
    });
    expect(
      resolveAuthOrigin(allowedRequest, { NEXTAUTH_URL: "http://localhost:3000" })
    ).toMatchObject({
      ok: false,
      reason: "static-auth-url"
    });
  });

  it("accepts a separately configured local browser origin", () => {
    const origin = "http://localhost:3000";
    expect(
      resolveAuthOrigin(request(`${origin}/api/auth/providers`), {
        AUTH_ALLOWED_ORIGINS: origin
      })
    ).toEqual({ ok: true, origin });
  });

  it.each(["javascript://localhost:3000", "http://localhost:3000/path"])(
    "rejects unsafe configured allowed origin %s",
    (origin) => {
      expect(
        resolveAuthOrigin(request(`${origin}/api/auth/providers`), {
          AUTH_ALLOWED_ORIGINS: origin
        }).ok
      ).toBe(false);
    }
  );

  it("rejects credentials in a configured origin without accepting the request URL", () => {
    expect(
      resolveAuthOrigin(request("http://localhost:3000/api/auth/providers"), {
        AUTH_ALLOWED_ORIGINS: "http://user:pass@localhost:3000"
      }).ok
    ).toBe(false);
  });

  it("only builds same-origin logout redirects", () => {
    expect(sameOriginAuthRedirect("https://shekkarchi.ir", "/auth/sign-in")).toBe(
      "https://shekkarchi.ir/auth/sign-in"
    );
    expect(sameOriginAuthRedirect("https://shekkarchi.ir", "//attacker.example")).toBeNull();
    expect(sameOriginAuthRedirect("https://shekkarchi.ir", "https://attacker.example")).toBeNull();
  });

  it.each([
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://87.107.153.123:3000",
    "https://shekkarchi.ir"
  ])("Auth.js builds its action/callback base on %s", (origin) => {
    const req = request(`${origin}/api/auth/signin/keycloak`);
    const action = createActionURL(
      "signin",
      new URL(req.url).protocol,
      req.headers,
      {},
      {
        basePath: "/api/auth"
      }
    );
    expect(action.origin).toBe(origin);
    expect(new URL("/api/auth/callback/keycloak", action).origin).toBe(origin);
  });
});

describe("Auth.js security behavior", () => {
  it.each(["http://localhost:3000", "http://192.168.31.168:3000", "https://shekkarchi.ir"])(
    "keeps state and PKCE and returns callback to %s",
    async (origin) => {
      const host = new URL(origin).host;
      const config = {
        basePath: "/api/auth",
        secret: "test-only-secret-for-unit-tests",
        trustHost: true,
        providers: [
          {
            id: "keycloak",
            name: "Keycloak",
            type: "oidc" as const,
            issuer: "https://identity.example/realms/test",
            clientId: "test-client",
            authorization: "https://identity.example/authorize",
            token: "https://identity.example/token",
            userinfo: "https://identity.example/userinfo",
            checks: ["state", "pkce"] as const
          }
        ]
      } satisfies AuthConfig;
      const csrfResponse = await Auth(
        new Request(`${origin}/api/auth/csrf`, { headers: { host } }),
        config
      );
      const csrf = ((await csrfResponse.json()) as { csrfToken: string }).csrfToken;
      const csrfCookie = csrfResponse.headers.get("set-cookie")?.split(";", 1)[0];
      const response = await Auth(
        new Request(`${origin}/api/auth/signin/keycloak`, {
          method: "POST",
          headers: {
            host,
            cookie: csrfCookie ?? "",
            "content-type": "application/x-www-form-urlencoded"
          },
          body: new URLSearchParams({ csrfToken: csrf })
        }),
        config
      );

      const location = new URL(response.headers.get("location")!);
      expect(location.searchParams.get("redirect_uri")).toBe(
        `${origin}/api/auth/callback/keycloak`
      );
      expect(location.searchParams.get("state")).toBeTruthy();
      expect(location.searchParams.get("code_challenge")).toBeTruthy();
      expect(location.searchParams.get("code_challenge_method")).toBe("S256");
      expect(response.headers.get("set-cookie")).toContain("authjs.state");
      expect(response.headers.get("set-cookie")).toContain("authjs.pkce.code_verifier");
    }
  );

  it.each([
    ["http://localhost:3000", false],
    ["http://192.168.31.168:3000", false],
    ["https://shekkarchi.ir", true]
  ])("uses cookie security appropriate to %s", async (origin, secure) => {
    const response = await Auth(
      new Request(`${origin}/api/auth/csrf`, { headers: { host: new URL(origin).host } }),
      {
        basePath: "/api/auth",
        secret: "test-only-secret-for-unit-tests",
        trustHost: true,
        providers: []
      }
    );
    const cookie = response.headers.get("set-cookie") ?? "";
    expect(cookie.includes("__Host-authjs.csrf-token")).toBe(secure);
    expect(cookie.includes("Secure")).toBe(secure);
  });
});
