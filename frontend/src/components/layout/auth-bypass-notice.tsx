'use client';

import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
import { Icons } from '@/components/icons';

/**
 * Stand-in for a Clerk-hosted UI (OrganizationList, OrganizationProfile,
 * UserProfile, PricingTable) while the local-dev auth bypass is on.
 *
 * Those components read Clerk context directly and throw when it is absent --
 * and `ClerkProvider` is deliberately not mounted under
 * `NEXT_PUBLIC_AUTH_BYPASS` (see providers.tsx). Rather than scatter a branch
 * through every page, they render this instead, so local development stays
 * navigable without pretending a real session exists.
 *
 * Never rendered in production: the flag is a local-dev convenience only.
 */
export function AuthBypassNotice({
  title,
  description
}: {
  title: string;
  description: string;
}) {
  return (
    <Empty className='border'>
      <EmptyHeader>
        <EmptyMedia variant='icon'>
          <Icons.lock />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}
