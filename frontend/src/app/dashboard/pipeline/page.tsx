import type { Metadata } from 'next';
import PipelinePage from '@/features/ops/components/pipeline-page';

export const metadata: Metadata = {
  title: "Dashboard : پایپ‌لاین پنج فاز",
  robots: { index: false, follow: false }
};

export default function Page() {
  return <PipelinePage />;
}
