import type { Metadata } from "next";
import { LandingPage } from "@/features/landing/components/landing-page";

export const metadata: Metadata = {
  title: { absolute: "شکارچی | SHEKARCHI — تحلیل هوشمند بازار املاک" },
  description:
    "شکارچی برای بازار املاک ایران؛ تحلیل AVM، رادار قیمت و نقشه در شهرها و محله‌های دارای داده.",
  openGraph: {
    title: "شکارچی | SHEKARCHI",
    description: "دیدی روشن‌تر به بازار املاک؛ تحلیل محله‌ها، ارزش‌گذاری و رادار قیمت.",
    locale: "fa_IR",
    type: "website"
  }
};

export default function Page() {
  return <LandingPage />;
}
