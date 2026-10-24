import type { Metadata } from 'next';
import PiiAuditPage from '@/features/crm/components/pii-audit-page';

export const metadata: Metadata = {
  title: "Dashboard : لاگ ممیزی",
  robots: { index: false, follow: false }
};

export default function Page() {
  return <PiiAuditPage />;
}
