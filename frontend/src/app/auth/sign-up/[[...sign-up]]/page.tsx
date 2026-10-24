import { Metadata } from 'next';
import MobileRegistrationView from '@/features/auth/components/mobile-registration-view';

export const metadata: Metadata = {
  title: 'ثبت‌نام در شکارچی',
  description: 'ثبت‌نام سریع با کد یک‌بارصرف موبایل در سامانهٔ مدیریت املاک شکارچی.'
};

export default function Page() {
  return <MobileRegistrationView />;
}
