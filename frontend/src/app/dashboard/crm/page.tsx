import type { Metadata } from 'next';
import CrmBoardPage from '@/features/crm/components/crm-board-page';

export const metadata: Metadata = {
  title: "Dashboard : CRM board",
  robots: { index: false, follow: false }
};

export default function Page() {
  return <CrmBoardPage />;
}
