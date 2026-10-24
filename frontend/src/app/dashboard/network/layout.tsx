import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Dashboard : شبکه همکاری دفاتر',
  robots: { index: false, follow: false }
};

export default function NetworkLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}