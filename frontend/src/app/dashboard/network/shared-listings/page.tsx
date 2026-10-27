import { NetworkPage } from "@/features/network/components/network-page";
import { Suspense } from "react";
import { ListSkeleton } from "@/features/network/components/shared";
import { SharedListingsView } from "./shared-listings-view";
import { sharedListingsInfoContent } from "./info-content";

export default function SharedListingsPage() {
  return (
    <NetworkPage
      pageTitle="فایل‌های اشتراکی"
      pageDescription="اشتراک‌های ارسالی و دریافتی فایل بین دفاتر، با لغو و تمدید"
      infoContent={sharedListingsInfoContent}
    >
      <Suspense fallback={<ListSkeleton rows={4} />}>
        <SharedListingsView />
      </Suspense>
    </NetworkPage>
  );
}
