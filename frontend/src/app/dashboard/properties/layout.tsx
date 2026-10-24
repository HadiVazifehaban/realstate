import KBar from '@/components/kbar';
import { InfoSidebar } from '@/components/layout/info-sidebar';
import { InfobarProvider } from '@/components/ui/infobar';

export default async function PropertiesLayout({ children }: { children: React.ReactNode }) {
  // No auth protection for /dashboard/properties - it's publicly accessible
  // This layout does NOT include sidebar - it uses the parent dashboard layout
  // but bypasses auth via the ApprovalGate with publicRoute=true

  return (
    <KBar>
      <InfobarProvider defaultOpen={false}>
        {children}
        <InfoSidebar side='left' />
      </InfobarProvider>
    </KBar>
  );
}
