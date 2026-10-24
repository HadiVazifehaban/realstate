import type { Metadata } from 'next';
import AwaitingApprovalPage from '@/features/auth/components/awaiting-approval-page';

export const metadata: Metadata = {
  title: "در انتظار تأیید",
  robots: { index: false, follow: false }
};

export default function Page() {
  return <AwaitingApprovalPage />;
}
