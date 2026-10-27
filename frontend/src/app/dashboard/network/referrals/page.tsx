import { NetworkPage } from "@/features/network/components/network-page";
import { ReferralsView } from "./referrals-view";
import { referralsInfoContent } from "./info-content";

export default function ReferralsPage() {
  return (
    <NetworkPage
      pageTitle="ارجاع‌ها"
      pageDescription="ارجاع مشتری و سرنخ بین دفاتر، با پیگیری مرحله تا نتیجه"
      infoContent={referralsInfoContent}
    >
      <ReferralsView />
    </NetworkPage>
  );
}
