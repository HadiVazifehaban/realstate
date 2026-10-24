import type { Metadata } from 'next';
import OtpManagementPage from '@/features/otp/components/otp-management-page';

export const metadata: Metadata = {
  title: 'Dashboard : مدیریت OTP',
  robots: { index: false, follow: false }
};

export default function Page() {
  return <OtpManagementPage />;
}
