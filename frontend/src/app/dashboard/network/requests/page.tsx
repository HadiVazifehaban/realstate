import { NetworkPage } from "@/features/network/components/network-page";
import { RequestsView } from "./requests-view";
import { requestsInfoContent } from "./info-content";

export default function RequestsPage() {
  return (
    <NetworkPage
      pageTitle="درخواست‌های همکاری"
      pageDescription="دریافتی، ارسالی، تأیید و رد درخواست‌های همکاری بین دفاتر"
      infoContent={requestsInfoContent}
    >
      <RequestsView />
    </NetworkPage>
  );
}
