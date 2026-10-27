import { NetworkPage } from "@/features/network/components/network-page";
import { CommissionsView } from "./commissions-view";
import { commissionsInfoContent } from "./info-content";

export default function CommissionsPage() {
  return (
    <NetworkPage
      pageTitle="کمیسیون و تسویه"
      pageDescription="توافق، سهم‌ها، پرداخت و تسویهٔ کمیسیون بین دفاتر"
      infoContent={commissionsInfoContent}
    >
      <CommissionsView />
    </NetworkPage>
  );
}
