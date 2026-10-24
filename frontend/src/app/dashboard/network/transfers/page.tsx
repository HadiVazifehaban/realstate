import PageContainer from '@/components/layout/page-container';
import { TransfersView } from './transfers-view';
import { transfersInfoContent } from './info-content';

export default function TransfersPage() {
  return (
    <PageContainer
      pageTitle='انتقال فایل‌ها'
      pageDescription='تاریخچهٔ انتقال مسئولیت فایل بین دفاتر با حفظ رگورد'
      infoContent={transfersInfoContent}
    >
      <TransfersView />
    </PageContainer>
  );
}
