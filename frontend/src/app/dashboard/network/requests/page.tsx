import PageContainer from '@/components/layout/page-container';
import { RequestsView } from './requests-view';
import { requestsInfoContent } from './info-content';

export default function RequestsPage() {
  return (
    <PageContainer
      pageTitle='درخواست‌های همکاری'
      pageDescription='دریافتی، ارسالی، تأیید و رد درخواست‌های همکاری بین دفاتر'
      infoContent={requestsInfoContent}
    >
      <RequestsView />
    </PageContainer>
  );
}
