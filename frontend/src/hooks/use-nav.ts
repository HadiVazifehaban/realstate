"use client";

/**
 * Fully client-side hook for filtering navigation items based on RBAC
 *
 * This hook uses Clerk's client-side hooks to check permissions, roles, and organization
 * without any server calls. This is perfect for navigation visibility (UX only).
 *
 * Performance:
 * - All checks are synchronous (no server calls)
 * - Instant filtering
 * - No loading states
 * - No UI flashing
 *
 * Note: For actual security (API routes, server actions), always use server-side checks.
 * This is only for UI visibility.
 */

import { AUTH_BYPASS_ENABLED, KEYCLOAK_ENABLED } from "@/lib/utils";
import { useMemo } from "react";
import { useOrganization, useUser } from "@clerk/nextjs";
import { useAuthContext } from "@/hooks/use-auth";
import type { NavItem, NavGroup } from "@/types";

const EMPTY_CONTEXT = {
  organization: undefined,
  user: undefined,
  permissions: [] as string[],
  role: undefined,
  allRoles: [] as string[],
  hasOrg: false
};

/**
 * Clerk's hooks throw when no provider is mounted, which is exactly the state
 * the local auth bypass creates. Rather than calling them conditionally inside
 * one hook (which would violate the rules of hooks), each mode gets its own
 * hook and the constant flag picks between them.
 *
 * Under the bypass the nav is simply unfiltered (no org, no permissions),
 * which is the correct local-development behaviour.
 */
function useBypassContext() {
  return EMPTY_CONTEXT;
}

function useClerkContext() {
  const { organization, membership } = useOrganization();
  const { user } = useUser();

  return useMemo(
    () => ({
      organization: organization ?? undefined,
      user: user ?? undefined,
      permissions: (membership?.permissions || []) as string[],
      role: membership?.role ?? undefined,
      allRoles: membership?.role ? [membership.role] : [],
      hasOrg: !!organization
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- stable primitives only
    [organization?.id, user?.id, membership?.permissions, membership?.role]
  );
}

/**
 * Keycloak mode: `<ClerkProvider />` is not mounted, so the Clerk hooks above
 * cannot run. The realm issues a `tenant_id` claim instead of an organization,
 * so `requireOrg` maps onto 'the token names a tenant' and realm roles stand in
 * for the Clerk membership role. This stays a visibility filter only — the API
 * re-derives both from the signed token.
 */
function useKeycloakContext() {
  const { tenantId, roles } = useAuthContext();

  return useMemo(
    () => ({
      organization: tenantId ?? undefined,
      user: undefined,
      permissions: [] as string[],
      role: roles.find((r) => !r.startsWith("default-")),
      allRoles: roles.filter((r) => !r.startsWith("default-roles")),
      hasOrg: !!tenantId
    }),
    [tenantId, roles]
  );
}

/** Resolves the access context for whichever auth mode is active. */
function useAccessContext() {
  if (AUTH_BYPASS_ENABLED) return useBypassContext();
  if (KEYCLOAK_ENABLED) return useKeycloakContext();
  return useClerkContext();
}

/**
 * Hook to filter navigation items based on RBAC (fully client-side)
 *
 * @param items - Array of navigation items to filter
 * @returns Filtered items
 */
export function useFilteredNavItems(items: NavItem[]) {
  const accessContext = useAccessContext();

  // Filter items synchronously (all client-side)
  const filteredItems = useMemo(() => {
    const filterTree = (nodes: NavItem[]): NavItem[] =>
      nodes
        .filter((item) => {
          // No access restrictions
          if (!item.access) {
            return true;
          }

          // Check requireOrg
          if (item.access.requireOrg && !accessContext.hasOrg) {
            return false;
          }

          // Check permission
          if (item.access.permission) {
            if (!accessContext.hasOrg) {
              return false;
            }
            if (!accessContext.permissions.includes(item.access.permission)) {
              return false;
            }
          }

          // Check role
          if (item.access.role) {
            if (!accessContext.hasOrg) {
              return false;
            }
            if (accessContext.role !== item.access.role) {
              return false;
            }
          }

          // Check any-of roles (plural). Visible when the caller holds at least
          // one of the listed roles — the gate an "admin block" needs, since a
          // single exact `role` match cannot express "admin OR supervisor".
          if (item.access.roles && item.access.roles.length > 0) {
            const holds = item.access.roles.some((r) => accessContext.allRoles.includes(r));
            if (!holds) {
              return false;
            }
          }

          // Note: Plans and features require server-side checks with Clerk's has() function
          // For navigation visibility, you can either:
          // 1. Store plan/feature info in organization metadata (client-accessible)
          // 2. Use server actions (current approach)
          // 3. Skip plan/feature checks for navigation (recommended for performance)

          // For now, if plan/feature is specified, we'll need to handle it differently
          // Most navigation items won't need plan/feature checks anyway
          if (item.access.plan || item.access.feature) {
            // Option: Return true and let the page handle it, or use server action
            // For now, we'll show it (page-level protection should handle it)
            console.warn(
              `Plan/feature checks for navigation items require server-side verification. ` +
                `Item '${item.title}' will be shown, but page-level protection should be implemented.`
            );
          }

          return true;
        })
        .map((item) => ({
          ...item,
          ...(item.items ? { items: filterTree(item.items) } : {})
        }));
    return filterTree(items);
  }, [items, accessContext]);

  return filteredItems;
}

/**
 * Hook to filter navigation groups based on RBAC (fully client-side)
 *
 * @param groups - Array of navigation groups to filter
 * @returns Filtered groups (empty groups are removed)
 */
export function useFilteredNavGroups(groups: NavGroup[]) {
  const allItems = useMemo(() => groups.flatMap((g) => g.items), [groups]);
  const filteredItems = useFilteredNavItems(allItems);

  return useMemo(() => {
    const filteredSet = new Set(filteredItems.map((item) => item.title));
    return groups
      .map((group) => ({
        ...group,
        items: filteredItems.filter((item) =>
          group.items.some((gi) => gi.title === item.title && filteredSet.has(gi.title))
        )
      }))
      .filter((group) => group.items.length > 0);
  }, [groups, filteredItems]);
}
