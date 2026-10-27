import { beforeEach, describe, expect, it, vi } from "vitest";

const { signIn } = vi.hoisted(() => ({ signIn: vi.fn() }));
vi.mock("next-auth/react", () => ({ signIn }));

import { beginKeycloakSignIn, resolveCallbackUrl } from "./keycloak-sign-in";

describe("Keycloak authentication entry", () => {
  beforeEach(() => signIn.mockReset());

  it("requests Keycloak's standard OIDC registration prompt", async () => {
    await beginKeycloakSignIn({ registration: true, callbackUrl: "/dashboard" });

    expect(signIn).toHaveBeenCalledWith(
      "keycloak",
      { callbackUrl: "/dashboard" },
      { prompt: "create" }
    );
  });

  it("keeps registration callbacks same-origin", () => {
    expect(resolveCallbackUrl("?callbackUrl=%2Fdashboard%3Ftab%3Dhome")).toBe(
      "/dashboard?tab=home"
    );
    expect(resolveCallbackUrl("?callbackUrl=https%3A%2F%2Fevil.example")).toBe(
      "/dashboard"
    );
  });
});
