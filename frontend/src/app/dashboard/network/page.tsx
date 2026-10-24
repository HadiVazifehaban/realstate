import PageContainer from '@/components/layout/page-container';
import { NetworkDashboard } from './network-dashboard';
import { networkInfoContent } from './info-content';

export default function NetworkPage() {
  return (
    <PageContainer
      pageTitle='شبکه همکاری دفاتر'
      pageDescription='مدیریت همکاری، اشتراک فایل و تسویهٔ کمیسیون بین دفاتر'
      infoContent={networkInfoContent}
    >
      <NetworkDashboard />
    </PageContainer>
  );
}
