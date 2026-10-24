import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
vi.mock("@/lib/utils", () => ({ AUTH_BYPASS_ENABLED: false, KEYCLOAK_ENABLED: true }));
vi.mock("@/hooks/use-auth", () => ({
  useAuthContext: () => ({ tenantId: "tenant", roles: ["ROLE_JUNIOR_BROKER"] })
}));
import { useFilteredNavItems } from "./use-nav";

describe("recursive navigation access", () => {
  it("applies the existing role rules at every depth without mutating the configuration", () => {
    const items = [
      {
        title: "parent",
        url: "/parent",
        items: [
          {
            title: "child",
            url: "/child",
            items: [
              { title: "hidden", url: "/hidden", access: { roles: ["ROLE_ADMIN"] } },
              { title: "visible", url: "/visible" }
            ]
          }
        ]
      }
    ];
    const { result } = renderHook(() => useFilteredNavItems(items));
    expect(result.current[0].items?.[0].items?.map((i) => i.title)).toEqual(["visible"]);
    expect(items[0].items[0].items).toHaveLength(2);
  });
});
