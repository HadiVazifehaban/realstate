import type { Metadata } from "next";
import CrmBoardPage from "@/features/crm/components/crm-board-page";

export const metadata: Metadata = {
  title: "میز کار معاملات | شکارچی",
  robots: { index: false, follow: false }
};

export default function Page() {
  return <CrmBoardPage />;
}
