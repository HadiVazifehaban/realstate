import type { Metadata } from 'next';
import PropertyDetailPage from '@/features/properties/components/property-detail-page';

export const metadata: Metadata = {
  title: "Dashboard : Property detail",
  robots: { index: false, follow: false }
};

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  // Resolving params here keeps the client component a plain prop consumer.
  const { id } = await params;

  return <PropertyDetailPage propertyId={id} />;
}
