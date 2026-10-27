'use client';

import { CLERK_ENABLED } from '@/lib/utils';
import { Icons } from '@/components/icons';
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar
} from '@/components/ui/sidebar';
import { useAuth, useOrganizationList } from '@clerk/nextjs';
import Image from 'next/image';
import { useRouter } from 'next/navigation';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import { useEffect } from 'react';
import { useCallback, useState } from 'react';
import { clearActiveWorkspaceId, fetchWorkspaces, getActiveWorkspaceId, setActiveWorkspaceId, setWorkspaceHeaderOverride, type Workspace } from '@/features/network/api/client';

/**
 * Renders the office switcher.
 *
 * Unless Clerk is the live provider there is no Clerk session and no
 * organization to switch between, so nothing is rendered -- the Clerk hooks
 * would throw without a provider, and a placeholder office label only
 * duplicated the logo already sitting above this in the sidebar header.
 * Under Keycloak the tenant comes from the token instead of a switchable list.
 */
export function OrgSwitcher() {
  if (CLERK_ENABLED) return <ClerkOrgSwitcher />;
  return <KeycloakWorkspaceSwitcher />;
}

function KeycloakWorkspaceSwitcher() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await fetchWorkspaces();
      setWorkspaces(result);
      const stored = getActiveWorkspaceId();
      const selected = result.length === 1
        ? result[0].id
        : result.some((workspace) => workspace.id === stored)
        ? stored
        : null;
      if (selected) setActiveWorkspaceId(selected);
      else if (stored) clearActiveWorkspaceId();
      setWorkspaceHeaderOverride(selected);
      setActiveId(selected);
    } catch {
      setError('بارگذاری دفاتر ناموفق بود');
      setWorkspaceHeaderOverride(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const changed = () => setActiveId(getActiveWorkspaceId());
    window.addEventListener('shekarchi:workspace-changed', changed);
    return () => window.removeEventListener('shekarchi:workspace-changed', changed);
  }, [refresh]);

  const active = workspaces.find((workspace) => workspace.id === activeId);
  if (loading) return <div className='px-3 py-2 text-xs text-muted-foreground'>در حال بارگذاری دفاتر…</div>;
  if (error) return <button className='px-3 py-2 text-xs text-destructive' onClick={() => void refresh()}>{error} · تلاش مجدد</button>;
  if (workspaces.length === 0) return null;

  return (
    <div className='px-2 py-1'>
      <label className='sr-only' htmlFor='keycloak-workspace-select'>انتخاب دفتر</label>
      <select
        id='keycloak-workspace-select'
        className='w-full rounded-md border bg-background px-2 py-2 text-sm'
        value={activeId ?? ''}
        onChange={(event) => {
          setActiveWorkspaceId(event.target.value);
          setWorkspaceHeaderOverride(event.target.value);
          setActiveId(event.target.value);
          window.location.reload();
        }}
      >
        {workspaces.map((workspace) => (
          <option key={workspace.id} value={workspace.id}>
            {workspace.name_fa || workspace.name} · {workspace.role}
          </option>
        ))}
      </select>
      {!active && workspaces.length > 1 && <p className='mt-1 text-xs text-muted-foreground'>برای ادامه یک دفتر انتخاب کنید.</p>}
    </div>
  );
}

function ClerkOrgSwitcher() {
  const { isMobile, state } = useSidebar();
  const router = useRouter();
  const { isLoaded, setActive, userMemberships } = useOrganizationList({
    userMemberships: {
      infinite: true,
      keepPreviousData: false
    }
  });

  const { orgId } = useAuth();

  useEffect(() => {
    if (userMemberships?.revalidate) {
      void userMemberships.revalidate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only revalidate when org changes, not on every userMemberships ref change
  }, [orgId]);

  // Get the currently active organization
  const activeOrganization = userMemberships?.data?.find(
    (membership) => membership.organization.id === orgId
  )?.organization;

  // Handle organization switch
  const handleOrganizationSwitch = async (organizationId: string) => {
    if (orgId === organizationId || !setActive) {
      return; // Already active or setActive not available
    }
    try {
      await setActive({ organization: organizationId });
    } catch (error) {
      console.error('Failed to switch organization:', error);
    }
  };

  // Show loading state
  if (!isLoaded) {
    return (
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton size='lg' disabled>
            <div className='bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 shrink-0 items-center justify-center rounded-lg'>
              <Icons.galleryVerticalEnd className='size-4' />
            </div>
            <div
              className={`grid flex-1 text-start text-sm leading-tight transition-all duration-200 ease-in-out ${
                state === 'collapsed'
                  ? 'invisible max-w-0 overflow-hidden opacity-0'
                  : 'visible max-w-full opacity-100'
              }`}
            >
              <span className='truncate font-medium'>Loading...</span>
              <span className='text-muted-foreground truncate text-xs'>Organizations</span>
            </div>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    );
  }

  // Show create organization option if no organizations
  if (!userMemberships?.data || userMemberships.data.length === 0) {
    return (
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton
            size='lg'
            onClick={() => router.push('/dashboard/workspaces')}
            className='data-popup-open:bg-sidebar-accent data-popup-open:text-sidebar-accent-foreground'
          >
            <div className='bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 shrink-0 items-center justify-center overflow-hidden rounded-lg'>
              <Icons.add className='size-4' />
            </div>
            <div
              className={`grid flex-1 text-start text-sm leading-tight transition-all duration-200 ease-in-out ${
                state === 'collapsed'
                  ? 'invisible max-w-0 overflow-hidden opacity-0'
                  : 'visible max-w-full opacity-100'
              }`}
            >
              <span className='truncate font-medium'>Create organization</span>
              <span className='text-muted-foreground truncate text-xs'>Get started</span>
            </div>
            <Icons.chevronsUpDown
              className={`ml-auto transition-all duration-200 ease-in-out ${
                state === 'collapsed'
                  ? 'invisible max-w-0 opacity-0'
                  : 'visible max-w-full opacity-100'
              }`}
            />
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    );
  }

  // Use active organization or first organization as fallback
  const displayOrganization = activeOrganization || userMemberships.data[0]?.organization;

  if (!displayOrganization) {
    return null;
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <SidebarMenuButton
                size='lg'
                className='data-popup-open:bg-sidebar-accent data-popup-open:text-sidebar-accent-foreground'
              />
            }
          >
            <div className='bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 shrink-0 items-center justify-center overflow-hidden rounded-lg'>
              {displayOrganization.hasImage && displayOrganization.imageUrl ? (
                <Image
                  src={displayOrganization.imageUrl}
                  alt={displayOrganization.name}
                  width={32}
                  height={32}
                  className='size-full object-cover'
                />
              ) : (
                <Icons.galleryVerticalEnd className='size-4' />
              )}
            </div>
            <div
              className={`grid flex-1 text-start text-sm leading-tight transition-all duration-200 ease-in-out ${
                state === 'collapsed'
                  ? 'invisible max-w-0 overflow-hidden opacity-0'
                  : 'visible max-w-full opacity-100'
              }`}
            >
              <span className='truncate font-medium'>{displayOrganization.name}</span>
              <span className='text-muted-foreground truncate text-xs'>
                {userMemberships.data.find((m) => m.organization.id === displayOrganization.id)
                  ?.role || 'Organization'}
              </span>
            </div>
            <Icons.chevronsUpDown
              className={`ml-auto transition-all duration-200 ease-in-out ${
                state === 'collapsed'
                  ? 'invisible max-w-0 opacity-0'
                  : 'visible max-w-full opacity-100'
              }`}
            />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className='w-(--anchor-width) min-w-56 rounded-lg'
            align='start'
            side={isMobile ? 'bottom' : 'right'}
            sideOffset={4}
          >
            <DropdownMenuGroup>
              <DropdownMenuLabel className='text-muted-foreground text-xs'>
                Organizations
              </DropdownMenuLabel>
            </DropdownMenuGroup>
            <DropdownMenuGroup>
              {userMemberships.data.map((membership, index) => {
                const isActive = membership.organization.id === orgId;
                return (
                  <DropdownMenuItem
                    key={membership.id}
                    onClick={() => handleOrganizationSwitch(membership.organization.id)}
                    className='gap-2 p-2'
                  >
                    <div className='flex size-6 items-center justify-center overflow-hidden rounded-md border'>
                      {membership.organization.hasImage && membership.organization.imageUrl ? (
                        <Image
                          src={membership.organization.imageUrl}
                          alt={membership.organization.name}
                          width={24}
                          height={24}
                          className='size-full object-cover'
                        />
                      ) : (
                        <Icons.galleryVerticalEnd className='size-3.5 shrink-0' />
                      )}
                    </div>
                    {membership.organization.name}
                    {isActive && <Icons.check className='ml-auto size-4' />}
                    {!isActive && <DropdownMenuShortcut>⌘{index + 1}</DropdownMenuShortcut>}
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem
                className='gap-2 p-2'
                onClick={() => {
                  router.push('/dashboard/workspaces');
                }}
              >
                <div className='flex size-6 items-center justify-center rounded-md border bg-transparent'>
                  <Icons.add className='size-4' />
                </div>
                <div className='text-muted-foreground font-medium'>Add organization</div>
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
