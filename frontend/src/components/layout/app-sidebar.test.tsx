import * as React from 'react';
import { act, cleanup, render, screen } from '@testing-library/react';
import { renderToString } from 'react-dom/server';
import { hydrateRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => ({ mobile: false }));
vi.mock('@/hooks/use-mobile', () => ({ useIsMobile: () => state.mobile }));
vi.mock('next/navigation', () => ({
  usePathname: () => '/dashboard/properties',
  useRouter: () => ({ push: vi.fn() })
}));
vi.mock('@/hooks/use-auth', () => ({
  useAuthUser: () => null,
  useAuthOrganization: () => null,
  useAuthSignOut: () => vi.fn()
}));
vi.mock('@/hooks/use-nav', () => ({ useFilteredNavGroups: (groups: unknown) => groups }));
vi.mock('@/components/org-switcher', () => ({ OrgSwitcher: () => null }));
vi.mock('@/components/brand/logo', () => ({ Logo: () => <span>شکارچی</span> }));

import AppSidebar from './app-sidebar';
import { SidebarProvider } from '@/components/ui/sidebar';

function Sidebar() {
  return <SidebarProvider defaultOpen={false}><AppSidebar /></SidebarProvider>;
}

describe('Keycloak dashboard sidebar rendering', () => {
  afterEach(() => { cleanup(); state.mobile = false; });

  it('uses one button for a collapsed menu trigger in server HTML', () => {
    const html = renderToString(<Sidebar />);
    const tags = html.match(/<\/?button\b[^>]*>/g) ?? [];
    let depth = 0;
    for (const tag of tags) {
      depth += tag.startsWith('</') ? -1 : 1;
      expect(depth).toBeGreaterThanOrEqual(0);
      expect(depth).toBeLessThanOrEqual(1);
    }
    expect(depth).toBe(0);
    expect(html).toContain('data-sidebar="menu-button"');
  });

  it('hydrates collapsed sidebar HTML without recoverable errors', async () => {
    const container = document.createElement('div');
    container.innerHTML = renderToString(<Sidebar />);
    document.body.append(container);
    const onRecoverableError = vi.fn();
    let root: ReturnType<typeof hydrateRoot>;
    await act(async () => { root = hydrateRoot(container, <Sidebar />, { onRecoverableError }); });
    expect(onRecoverableError).not.toHaveBeenCalled();
    await act(async () => root!.unmount());
    container.remove();
  });

  it('preserves hook ordering when the viewport switches to mobile', () => {
    const { rerender } = render(<Sidebar />);
    expect(screen.getByText('خروج')).not.toBeNull();
    state.mobile = true;
    expect(() => rerender(<Sidebar />)).not.toThrow();
    expect(screen.queryByText('خروج')).toBeNull();
  });
});