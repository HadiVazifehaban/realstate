import PageContainer from '@/components/layout/page-container';
import { ReferralsView } from './referrals-view';
import { referralsInfoContent } from './info-content';

export default function ReferralsPage() {
  return (
    <PageContainer
      pageTitle='ارجاع‌ها'
      pageDescription='ارجاع مشتری و سرنخ بین دفاتر، با پیگیری مرحله تا نتیجه'
      infoContent={referralsInfoContent}
    >
      <ReferralsView />
    </PageContainer>
  );
}
