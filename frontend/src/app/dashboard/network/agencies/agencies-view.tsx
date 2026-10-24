'use client';

import { useAuthContext } from '@/hooks/use-auth';
import { NetworkAgenciesList } from './components/network-agencies-list';

/**
 * Wrapper که شناسهٔ دفترِ جاری (tenant) را از session می‌خواند و به لیست می‌دهد.
 * `tenantId` همان شناسه‌ای است که بک‌اند به‌عنوان agency_id می‌شناسد.
 */
export function AgenciesView() {
  const auth = useAuthContext();
  return <NetworkAgenciesList currentAgencyId={auth.tenantId} />;
}
