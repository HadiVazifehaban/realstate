import PageContainer from '@/components/layout/page-container';
import { DisputesView } from './disputes-view';
import { disputesInfoContent } from './info-content';

export default function DisputesPage() {
  return (
    <PageContainer
      pageTitle='اختلافات'
      pageDescription='ثبت و پیگیری اختلاف بین دفاتر، با پیام و وضعیت'
      infoContent={disputesInfoContent}
    >
      <DisputesView />
    </PageContainer>
  );
}
