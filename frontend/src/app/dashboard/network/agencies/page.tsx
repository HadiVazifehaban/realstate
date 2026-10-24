import PageContainer from '@/components/layout/page-container';
import { AgenciesView } from './agencies-view';
import { agenciesInfoContent } from './info-content';

export default function AgenciesPage() {
  return (
    <PageContainer
      pageTitle='دفاتر همکار'
      pageDescription='فهرست، جستجو و ارسال درخواست همکاری به دفاتر شبکه'
      infoContent={agenciesInfoContent}
    >
      <AgenciesView />
    </PageContainer>
  );
}
