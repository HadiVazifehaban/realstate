"use client";

import { useRouter, usePathname } from 'next/navigation';
import * as React from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuthContext } from '@/hooks/use-auth';
import { AUTH_BYPASS_ENABLED, KEYCLOAK_ENABLED } from '@/lib/utils';

/**
 * Client-side approval gate for the `/dashboard` segment.
 *
 * The real enforcement lives in the FastAPI core, which rejects a PENDING token
 * with 403 no matter what the browser renders. This gate exists so a pending
 * user sees the explanation instead of a wall of failed requests.
 *
 * While the token is still being fetched the children are withheld rather than
 * flashed, so no protected markup is ever painted before the check resolves.
 */
export function ApprovalGate({ children, publicRoute = false }: { children: React.ReactNode; publicRoute?: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isApproved, isLoading } = useAuthContext();

  // Properties and submit routes are always public
  const isPropertiesRoute = pathname.startsWith('/dashboard/properties');
  const finalPublicRoute = publicRoute || isPropertiesRoute;

  // Outside a Keycloak deployment there is no KYC concept to enforce here.
  // Both flags are build-time constants, so this branch is stable per build and
  // the hook order below never changes between renders.
  const enforced = !finalPublicRoute && KEYCLOAK_ENABLED && !AUTH_BYPASS_ENABLED;

  // The realm session is fetched client-side, so the claims read as PENDING
  // until it lands. Redirecting on that would bounce a verified user out of the
  // desk before the answer arrived, so hold the skeleton while it resolves.
  React.useEffect(() => {
    if (enforced && !isLoading && !isApproved) router.replace("/awaiting-approval");
  }, [enforced, isLoading, isApproved, router]);

  if (!enforced) return <>{children}</>;

  if (isLoading || !isApproved) return <Skeleton className='h-64 w-full' />;

  return <>{children}</>;
}
