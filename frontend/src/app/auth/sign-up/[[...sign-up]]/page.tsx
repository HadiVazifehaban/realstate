import { Metadata } from 'next';
import { VerifiedRegistrationView } from '@/features/auth/components/verified-registration-view';
import MobileRegistrationView from '@/features/auth/components/mobile-registration-view';
import { KEYCLOAK_ENABLED } from '@/lib/utils';

export const metadata: Metadata = {
  title: 'ثبت‌نام در شکارچی',
  description: 'ثبت‌نام سریع با کد یک‌بارصرف موبایل در سامانهٔ مدیریت املاک شکارچی.'
};

export default function Page() {
  return KEYCLOAK_ENABLED ? <VerifiedRegistrationView /> : <MobileRegistrationView />;
}
