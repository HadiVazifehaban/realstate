// @vitest-environment node
import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { normalizeAuthRequest } from "./request-origin";

function incoming(headers: Record<string, string> = {}, method = "GET") {
  return new NextRequest("http://0.0.0.0:3000/api/auth/providers?test=1", {
    method,
    headers: {
      host: "localhost:3000",
      "x-forwarded-host": "localhost:3000",
      "x-forwarded-proto": "http",
      "x-forwarded-port": "3000",
      "x-forwarded-for": "172.18.0.1",
      ...headers
    },
    ...(method === "POST" ? { body: "csrfToken=test", duplex: "half" as const } : {})
  });
}

describe("Auth route normalization", () => {
  it("accepts actual Next.js direct-request headers and normalizes the internal URL", () => {
    const result = normalizeAuthRequest(incoming());
    expect(result?.url).toBe("http://localhost:3000/api/auth/providers?test=1");
    expect(result?.headers.get("x-forwarded-for")).toBeNull();
  });
  it.each<Record<string, string>>([
    { host: "attacker.example" },
    { "x-forwarded-host": "attacker.example" },
    { "x-forwarded-proto": "https" },
    { "x-forwarded-port": "444" },
    { origin: "https://attacker.example" },
    { origin: "https://shekkarchi.ir" },
    { forwarded: "host=attacker.example" },
    { "x-original-host": "attacker.example" }
  ])("rejects inconsistent routing metadata %j", (headers) => {
    expect(normalizeAuthRequest(incoming(headers))).toBeNull();
  });
  it("does not choose callback origin from Referer", () => {
    const result = normalizeAuthRequest(incoming({ referer: "https://attacker.example/" }));
    expect(new URL(result!.url).origin).toBe("http://localhost:3000");
  });
  it("preserves POST body for Auth.js CSRF verification", async () => {
    const result = normalizeAuthRequest(incoming({ origin: "http://localhost:3000" }, "POST"));
    expect(await result?.text()).toBe("csrfToken=test");
  });
});