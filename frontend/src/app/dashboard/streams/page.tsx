import type { Metadata } from 'next';
import StreamsPage from '@/features/ops/components/streams-page';

export const metadata: Metadata = {
  title: "Dashboard : صف جاوب",
  robots: { index: false, follow: false }
};

export default function Page() {
  return <StreamsPage />;
}
