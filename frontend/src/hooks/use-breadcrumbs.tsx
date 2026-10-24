'use client';

import { usePathname } from 'next/navigation';
import { useMemo } from 'react';

import { navGroups } from '@/config/nav-config';
import type { NavItem } from '@/types';

type BreadcrumbItem = {
  title: string;
  link: string;
};

/** Walks the sidebar tree, however deep a submenu happens to nest. */
function collectTitles(items: NavItem[], map: Record<string, string>): void {
  for (const item of items) {
    if (item.url.startsWith('/')) map[item.url] = item.title;
    if (item.items?.length) collectTitles(item.items, map);
  }
}

/** Every navigable URL in the sidebar, flattened once: path -> Persian title. */
const navTitles: Record<string, string> = (() => {
  const map: Record<string, string> = {};
  for (const group of navGroups) collectTitles(group.items, map);
  return map;
})();

/**
 * Breadcrumb labels for the current route.
 *
 * The sidebar already names every screen in Persian, so the crumb reads from
 * that configuration rather than from the URL. Deriving it from the path
 * capitalised the raw segment, which printed `Submit` and `Avm` above a
 * fully-Persian page.
 *
 * A segment with no configured title keeps the old capitalised form: a route
 * that exists but is not in the sidebar is still better labelled than blank.
 */
export function useBreadcrumbs() {
  const pathname = usePathname();

  return useMemo(() => {
    const segments = pathname.split('/').filter(Boolean);

    const crumbs: BreadcrumbItem[] = segments.map((segment, index) => {
      const link = `/${segments.slice(0, index + 1).join('/')}`;
      return {
        title:
          navTitles[link] ?? segment.charAt(0).toUpperCase() + segment.slice(1),
        link
      };
    });

    // The dashboard root is a real destination, so it leads the trail rather
    // than being spelled out segment by segment.
    if (crumbs[0]?.link === '/dashboard') {
      crumbs[0] = { title: navTitles['/dashboard'] ?? 'داشبورد', link: '/dashboard' };
    }

    return crumbs;
  }, [pathname]);
}
