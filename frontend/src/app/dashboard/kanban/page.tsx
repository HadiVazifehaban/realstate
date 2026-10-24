import { redirect } from 'next/navigation';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Dashboard : تخته کانبان لیدها',
  robots: { index: false, follow: false }
};

/**
 * Merged into `/dashboard/crm`.
 *
 * Both routes rendered the same `CrmBoardPage` (the CRM `LeadStage` state
 * machine), so keeping two menu entries only duplicated the sidebar.
 * This route stays as a redirect so old bookmarks keep working.
 */
export default function page() {
  redirect('/dashboard/crm');
}
