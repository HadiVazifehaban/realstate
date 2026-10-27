import { NetworkPage } from "@/features/network/components/network-page";
import { AgenciesView } from "./agencies-view";
import { agenciesInfoContent } from "./info-content";

export default function AgenciesPage() {
  return (
    <NetworkPage
      pageTitle="دفاتر همکار"
      pageDescription="فهرست، جستجو و ارسال درخواست همکاری به دفاتر شبکه"
      infoContent={agenciesInfoContent}
    >
      <AgenciesView />
    </NetworkPage>
  );
}
