import type { Metadata } from 'next';
import CrmEventsPage from '@/features/crm/components/crm-events-page';

export const metadata: Metadata = {
  title: "Dashboard : رویدادهای CRM",
  robots: { index: false, follow: false }
};

export default function Page() {
  return <CrmEventsPage />;
}
