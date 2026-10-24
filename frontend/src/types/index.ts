import { Icons } from '@/components/icons';

export interface PermissionCheck {
  permission?: string;
  plan?: string;
  feature?: string;
  role?: string;
  /**
   * Any-of role gate. The item is visible when the caller holds at least one of
   * these realm roles. This is the plural companion to `role` (which is an exact
   * single match) and is what an "admin block" needs — e.g. `['ROLE_ADMIN',
   * 'ROLE_SUPERVISOR']`. Under Keycloak these are realm roles; under Clerk the
   * membership role. Visibility only — the API re-derives access from the token.
   */
  roles?: string[];
  requireOrg?: boolean;
}

export interface NavItem {
  title: string;
  url: string;
  disabled?: boolean;
  external?: boolean;
  shortcut?: [string, string];
  icon?: keyof typeof Icons;
  label?: string;
  /**
   * Small status chip shown at the inline-end of the row (e.g. «زنده», «جدید»,
   * «به‌زودی»). Rendered by the sidebar as a subtle glass Badge; the Cmd+K bar
   * and breadcrumbs ignore it. Prefer this over overloading `label`, which the
   * SidebarGroup already uses for section headings.
   */
  badge?: string;
  description?: string;
  isActive?: boolean;
  items?: NavItem[];
  access?: PermissionCheck;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export interface NavItemWithChildren extends NavItem {
  items: NavItemWithChildren[];
}

export interface NavItemWithOptionalChildren extends NavItem {
  items?: NavItemWithChildren[];
}

export interface FooterItem {
  title: string;
  items: {
    title: string;
    href: string;
    external?: boolean;
  }[];
}

export type MainNavItem = NavItemWithOptionalChildren;

export type SidebarNavItem = NavItemWithChildren;
