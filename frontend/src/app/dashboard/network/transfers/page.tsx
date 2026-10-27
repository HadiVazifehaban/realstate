import { NetworkPage } from "@/features/network/components/network-page";
import { TransfersView } from "./transfers-view";
import { transfersInfoContent } from "./info-content";

export default function TransfersPage() {
  return (
    <NetworkPage
      pageTitle="انتقال فایل‌ها"
      pageDescription="تاریخچهٔ انتقال مسئولیت فایل بین دفاتر با حفظ سوابق"
      infoContent={transfersInfoContent}
    >
      <TransfersView />
    </NetworkPage>
  );
}
