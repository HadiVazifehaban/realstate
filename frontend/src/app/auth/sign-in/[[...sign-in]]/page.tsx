import { Metadata } from 'next';
import SignInViewPage from '@/features/auth/components/sign-in-view';

// Declared here rather than in the view: `page.tsx` metadata is the one Next
// reads, so exporting it from the view too would be a second source of truth
// that silently loses.
export const metadata: Metadata = {
  title: 'ورود به شکارچی',
  description: 'ورود کاربران سامانهٔ مدیریت املاک شکارچی.'
};

export default async function Page() {
  return <SignInViewPage />;
}
