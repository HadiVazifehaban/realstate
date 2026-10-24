import PageContainer from '@/components/layout/page-container';
import { SharedListingsView } from './shared-listings-view';
import { sharedListingsInfoContent } from './info-content';

export default function SharedListingsPage() {
  return (
    <PageContainer
      pageTitle='فایل‌های اشتراکی'
      pageDescription='اشتراک‌های ارسالی و دریافتی فایل بین دفاتر، با لغو و تمدید'
      infoContent={sharedListingsInfoContent}
    >
      <SharedListingsView />
    </PageContainer>
  );
}
