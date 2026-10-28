import { describe, expect, it } from "vitest";
import { isPublicRoute, requiredRolesForPage } from "./route-policy";

describe("landing route classification", () => {
  it("makes public inventory reads available, not orders or subscriptions", () => {
    expect(isPublicRoute("/backend/api/v1/billing/plans")).toBe(true);
    expect(isPublicRoute("/backend/api/v1/properties")).toBe(true);
    expect(isPublicRoute("/backend/api/v1/properties/cities")).toBe(true);
    expect(isPublicRoute("/backend/api/v1/properties/market/neighbourhoods")).toBe(true);
    for (const path of [
      "/backend/api/v1/billing/orders",
      "/backend/api/v1/billing/subscriptions/current",
      "/backend/api/v1/billing/plans/other"
    ]) {
      expect(isPublicRoute(path)).toBe(false);
    }
  });
  it("exposes only the exact public social path and gates management", () => {
    expect(isPublicRoute("/backend/api/v1/site/social-links")).toBe(true);
    expect(isPublicRoute("/backend/api/v1/site/social-links/other")).toBe(false);
    expect(isPublicRoute("/backend/api/v1/admin/social-links")).toBe(false);
    expect(requiredRolesForPage("/dashboard/settings/social-links")).toEqual([
      "ROLE_ADMIN",
      "ROLE_SUPER_ADMIN",
      "admin",
      "super_admin"
    ]);
  });
  it("exposes only the exact homepage and existing authentication pages", () => {
    for (const path of ["/", "/auth", "/auth/sign-in", "/auth/sign-up"]) {
      expect(isPublicRoute(path)).toBe(true);
    }
  });

  it.each([
    "/dashboard",
    "/dashboard/avm",
    "/dashboard/properties",
    "/dashboard/properties/submit",
    "/dashboard/billing",
    "/api/gis/static-map",
    "/backend/api/v1/properties/00000000-0000-0000-0000-000000000000",
    "/unknown",
    "//"
  ])("keeps %s protected", (path) => {
    expect(isPublicRoute(path)).toBe(false);
  });

  it("retains role-based restrictions on inventory, submissions and administration", () => {
    expect(requiredRolesForPage("/dashboard/roles")).toEqual(["ROLE_ADMIN"]);
    expect(requiredRolesForPage("/dashboard/properties")).not.toContain("ROLE_OWNER");
    expect(requiredRolesForPage("/dashboard/properties/submit")).toContain("ROLE_OWNER");
  });

  it("restricts every Keycloak administration page to the verified system admin role", () => {
    for (const path of [
      '/dashboard/settings/keycloak',
      '/dashboard/settings/keycloak/users',
      '/dashboard/settings/keycloak/clients'
    ]) {
      expect(requiredRolesForPage(path)).toEqual(['ROLE_ADMIN']);
    }
  });
});
