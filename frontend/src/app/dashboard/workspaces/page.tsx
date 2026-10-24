'use client';

import PageContainer from '@/components/layout/page-container';
import { officeInfoContent } from '@/features/workspaces/info-content';
import { PortfolioDesk } from '@/features/workspaces/components/portfolio-desk';

/**
 * The office this node serves.
 *
 * Two deployments, two answers. Under Clerk the starter's organization list is
 * still the workspace switcher; on a Keycloak/LOCAL node — one office, one
 * tenant claim, no second workspace to switch to — the page shows what is
 * actually knowable here: the licence, the caller's own access, and the roster.
 */
export default function WorkspacesPage() {
  return (
    <PageContainer
      pageTitle='کارتابل فایل‌های دفتر'
      pageDescription='موجودی، فرصت‌های شکار و پیگیری فایل‌های ملکی دفتر'
      infoContent={officeInfoContent}
    >
      <PortfolioDesk />
    </PageContainer>
  );
}
