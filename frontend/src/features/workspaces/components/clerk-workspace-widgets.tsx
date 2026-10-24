'use client';

/**
 * Clerk's organization widgets, kept in one client file.
 *
 * The dashboard's route files are server components (they export metadata), and
 * `@clerk/nextjs` components read Clerk context, which only exists under the
 * Clerk provider. Wrapping them here means the Keycloak/LOCAL deployment — this
 * node — never imports Clerk's runtime into the workspaces routes at all.
 */

import { OrganizationList, OrganizationProfile } from '@clerk/nextjs';

export function ClerkOrganizationList() {
  return (
    <OrganizationList
      appearance={{
        elements: {
          organizationListBox: 'space-y-2',
          organizationPreview: 'rounded-lg border p-4 hover:bg-accent',
          organizationPreviewMainIdentifier: 'text-lg font-semibold',
          organizationPreviewSecondaryIdentifier: 'text-sm text-muted-foreground'
        }
      }}
      afterSelectOrganizationUrl='/dashboard/workspaces/team'
      afterCreateOrganizationUrl='/dashboard/workspaces/team'
    />
  );
}

export function ClerkOrganizationProfile() {
  return <OrganizationProfile />;
}
