import PageContainer from '@/components/layout/page-container';
import { ReportsView } from './reports-view';
import { reportsInfoContent } from './info-content';

export default function ReportsPage() {
  return (
    <PageContainer
      pageTitle='گزارش‌های همکاری'
      pageDescription='شاخص‌های عملکرد و روند همکاری بین دفاتر'
      infoContent={reportsInfoContent}
    >
      <ReportsView />
    </PageContainer>
  );
}
