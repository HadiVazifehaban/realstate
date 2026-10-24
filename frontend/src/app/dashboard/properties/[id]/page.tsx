import type { Metadata } from 'next';
import PageContainer from '@/components/layout/page-container';
import PropertyDetailPage from '@/features/properties/components/property-detail-page';

export const metadata: Metadata = {
  title: "Dashboard : Property detail",
  robots: { index: false, follow: false }
};

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  // Resolving params here keeps the client component a plain prop consumer.
  const { id } = await params;

  return (
    <PageContainer pageTitle='جزئیات فایل'>
      <PropertyDetailPage propertyId={id} />
    </PageContainer>
  );
}
