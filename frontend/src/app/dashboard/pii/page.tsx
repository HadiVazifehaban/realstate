import type { Metadata } from 'next';
import PiiVaultPage from '@/features/crm/components/pii-vault-page';

export const metadata: Metadata = {
  title: "Dashboard : خزانه اطلاعات هویتی",
  robots: { index: false, follow: false }
};

export default function Page() {
  return <PiiVaultPage />;
}
