import type { Metadata } from 'next';

import PageContainer from '@/components/layout/page-container';
import { AgencyDetailClient } from './agency-detail-client';

export const metadata: Metadata = {
  title: 'Dashboard : پروفایل دفتر همکار',
  robots: { index: false, follow: false }
};

export default function AgencyDetailPage() {
  return (
    <PageContainer pageTitle='پروفایل دفتر همکار' pageDescription='جزئیات یک دفتر شبکه'>
      <AgencyDetailClient />
    </PageContainer>
  );
}
