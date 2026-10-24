import type { Metadata } from 'next';
import type { SearchParams } from 'nuqs/server';

import PageContainer from '@/components/layout/page-container';
import { searchParamsCache } from '@/lib/searchparams';
import { CLERK_ENABLED } from '@/lib/utils';
import UserListingPage from '@/features/users/components/user-listing';
import { usersInfoContent } from '@/features/users/info-content';
import { ClerkOrganizationProfile } from '@/features/workspaces/components/clerk-workspace-widgets';

export const metadata: Metadata = {
  title: 'Dashboard : تیم دفتر',
  robots: { index: false, follow: false }
};

type PageProps = {
  searchParams: Promise<SearchParams>;
};

/**
 * The desk's own roster.
 *
 * On a Keycloak node there is nothing for Clerk's organization profile to
 * render, so the page shows the users directory itself — the same listing,
 * prefetch and role histogram the «کاربران و نقش‌ها» page uses, minus the
 * second toolbar, because membership changes belong in one place.
 */
export default async function TeamPage(props: PageProps) {
  const searchParams = await props.searchParams;
  searchParamsCache.parse(searchParams);

  return (
    <PageContainer
      pageTitle='تیم دفتر'
      pageDescription='اعضای این دفتر و سطح دسترسی هرکدام'
      infoContent={usersInfoContent}
    >
      {CLERK_ENABLED ? <ClerkOrganizationProfile /> : <UserListingPage showRoleBreakdown />}
    </PageContainer>
  );
}
