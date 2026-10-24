import PageContainer from '@/components/layout/page-container';
import { AuditView } from './audit-view';
import { auditInfoContent } from './info-content';

export default function AuditPage() {
  return (
    <PageContainer
      pageTitle='رهگیری و لاگ'
      pageDescription='لاگ امنیتی رویدادهای حساس شبکه: افشا، خروجی، دسترسی، انتقال و مالی'
      infoContent={auditInfoContent}
    >
      <AuditView />
    </PageContainer>
  );
}
