import PageContainer from '@/components/layout/page-container';
import { CommissionsView } from './commissions-view';
import { commissionsInfoContent } from './info-content';

export default function CommissionsPage() {
  return (
    <PageContainer
      pageTitle='کمیسیون و تسویه'
      pageDescription='توافق، سهم‌ها، پرداخت و تسویهٔ کمیسیون بین دفاتر'
      infoContent={commissionsInfoContent}
    >
      <CommissionsView />
    </PageContainer>
  );
}
