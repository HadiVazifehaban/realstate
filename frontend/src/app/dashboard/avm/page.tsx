import type { Metadata } from 'next';
import AvmPage from '@/features/properties/components/avm-page';

export const metadata: Metadata = {
  title: "Dashboard : تحلیل بازار و ارزش‌گذاری",
  robots: { index: false, follow: false }
};

export default function Page() {
  return <AvmPage />;
}
