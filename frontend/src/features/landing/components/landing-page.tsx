import Image from "next/image";
import Link from "next/link";
import {
  IconArrowUpLeft,
  IconChartAreaLine,
  IconCrosshair,
  IconMap2,
  IconCheck,
  IconArrowDown,
  IconBuildingCommunity
} from "@tabler/icons-react";
import { LandingHeader } from "./landing-header";
import { landingRoutes } from "../config";
import "../landing.css";
import { DashboardAccess } from "./dashboard-access";
import { LandingPlans } from "./landing-plans";
import { ToolPreview } from "./tool-preview";
import { LandingListings } from "./landing-listings";
import { HeroAtmosphere } from "./hero-atmosphere";
import { LandingFooter } from "./landing-footer";
import { HeroOpportunity } from "./hero-opportunity";
import { HeroMarket } from "./hero-market";
import { LandingCityPicker } from "./landing-city-picker";

const tools = [
  {
    title: "تحلیل هوشمند و ارزش‌گذاری AVM",
    eyebrow: "AI · Automated Valuation",
    icon: IconChartAreaLine,
    preview: "chart",
    href: landingRoutes.avm,
    description:
      "مقایسهٔ قیمت فایل‌ها با میانهٔ محله و بررسی شاخص‌های بازار، بر پایهٔ داده‌های موجود در سامانه.",
    detail: ["ارزش‌گذاری ملک", "تحلیل محله‌ها", "مقایسهٔ قیمت"]
  },
  {
    title: "رادار شکار قیمت",
    eyebrow: "Price Radar · Properties",
    icon: IconCrosshair,
    preview: "radar",
    href: landingRoutes.radar,
    description: "مرور و فیلتر فایل‌های املاک؛ بررسی قیمت، مشخصات و نتیجهٔ ارزش‌گذاری در کنار یکدیگر.",
    detail: ["فیلتر فایل‌ها", "مقایسهٔ املاک", "بررسی قیمت"]
  },
  {
    title: "نقشهٔ تعاملی بازار املاک",
    eyebrow: "Market Map · Neighborhoods",
    icon: IconMap2,
    preview: "map",
    href: landingRoutes.map,
    description:
      "بررسی محله‌های دارای داده روی نقشهٔ تحلیل بازار؛ انتخاب محله و مرور فایل‌های مرتبط با آن.",
    detail: ["نقشهٔ محله‌ها", "تحلیل مکانی", "فایل‌های مرتبط"]
  }
] as const;

export function LandingPage({ dashboard = false }: { dashboard?: boolean }) {
  const Content = dashboard ? "div" : "main";
  return (
    <div className={`landing ${dashboard ? "landing-dashboard" : ""}`} dir="rtl">
      <a className="landing-skip" href="#landing-content">
        رفتن به محتوای اصلی
      </a>
      {!dashboard && <LandingHeader />}
      <Content id="landing-content" tabIndex={-1}>
        <section className="landing-hero" aria-labelledby="hero-heading">
          <Image
            className="landing-hero-image"
            src="/images/tehran-night-skyline.webp"
            unoptimized
            alt="چشم‌انداز شب تهران، برج میلاد و کوه‌های البرز"
            fill
            priority
            sizes="100vw"
          />
          <div className="landing-hero-shade" aria-hidden="true" />
          <HeroAtmosphere />
          <svg className="landing-circuit" viewBox="0 0 500 400" fill="none" aria-hidden="true">
            <path d="M0 70h110l40 40h80l50 50h200M40 270h90l65-65h130l45 45h130M80 390V330l45-45V120l55-55V0" />
            <circle cx="230" cy="110" r="5" />
            <circle cx="325" cy="205" r="5" />
            <circle cx="125" cy="285" r="5" />
          </svg>
          <div className="landing-hero-content landing-container">
            <LandingCityPicker />
            <h1 id="hero-heading">
              شکار هوشمند
              <br />
              <span>فرصت‌های ملکی</span> در سراسر ایران
            </h1>
            <p className="landing-hero-subtitle">
              پشت هر قیمت، داستانی هست.
              <br className="landing-mobile-break" /> بازار را روشن‌تر ببین.
            </p>
            <p className="landing-hero-description">
              با شکارچی، تحلیل بازار، ارزش‌گذاری خودکار ملک و رادار قیمت را کنار هم داشته باشید؛
              ابزارهایی برای بررسی آگاهانه‌تر املاک ایران. تحلیل و نقشه فقط در شهرها و محله‌های دارای
              داده ارائه می‌شوند؛ این تصویر شب تهران، محدودهٔ خدمات سامانه نیست.
            </p>
            <div className="landing-hero-actions">
              <Link href={landingRoutes.avm} className="landing-button landing-button-primary">
                ورود به تحلیل بازار <IconArrowUpLeft size={20} aria-hidden />
              </Link>
              <Link
                href={
                  dashboard
                    ? "#dashboard-access"
                    : landingRoutes.signIn + "?callbackUrl=%2Fdashboard"
                }
                className="landing-button landing-button-glass"
              >
                {dashboard ? "کاوش در بخش‌های سامانه" : "ورود به سامانه"}
              </Link>
            </div>
            <ul className="landing-benefits" aria-label="ابزارهای شکارچی">
              {["تحلیل بر پایهٔ داده‌های موجود", "فیلتر و مقایسهٔ فایل‌ها", "ابزارهای مشاوران"].map(
                (text) => (
                  <li key={text}>
                    <IconCheck size={15} aria-hidden />
                    {text}
                  </li>
                )
              )}
            </ul>
          </div>
          <HeroOpportunity />
          <HeroMarket />
          <div className="landing-hero-bottom landing-container">
            <span>بازار املاک ایران، از زاویه‌ای روشن‌تر</span>
            <a href="#professional-tools" aria-label="مشاهدهٔ ابزارهای حرفه‌ای">
              <IconArrowDown aria-hidden size={18} />
            </a>
            <span lang="en" dir="ltr">
              A CLEARER VIEW OF PROPERTY
            </span>
          </div>
        </section>

        <LandingListings />

        <section
          id="professional-tools"
          className="landing-tools landing-container"
          aria-labelledby="tools-heading"
        >
          <div className="landing-section-heading">
            <p className="landing-kicker">قابلیت‌های کلیدی</p>
            <p className="landing-tools-brand" dir="ltr">
              SMART REAL ESTATE SUITE
            </p>
            <h2 id="tools-heading">
              سه ابزار حرفه‌ای برای
              <br className="landing-mobile-break" /> <span>شکار فرصت‌های ملکی</span>
            </h2>
            <p>به‌جای حدس‌زدن، فایل‌ها و محله‌ها را از چند زاویه بررسی کنید.</p>
          </div>
          <div className="landing-tools-grid">
            {[tools[0], tools[2], tools[1]].map(
              ({ title, eyebrow, icon: Icon, href, description, detail, preview }) => (
                <article className="landing-tool-card" key={href}>
                  <ToolPreview kind={preview} />
                  <div className="landing-tool-top">
                    <Icon aria-hidden size={30} stroke={1.4} />
                    <span dir="ltr">{eyebrow}</span>
                  </div>
                  <h3>{title}</h3>
                  <p>{description}</p>
                  <ul className="landing-tool-detail">
                    {detail.map((label) => (
                      <li key={label}>{label}</li>
                    ))}
                  </ul>
                  <Link href={href}>
                    ورود به ابزار <IconArrowUpLeft aria-hidden size={20} />
                    <span className="sr-only"> {title}</span>
                  </Link>
                </article>
              )
            )}
          </div>
          <p className="landing-data-note">
            نتایج تحلیل به پوشش و کیفیت داده‌های ثبت‌شده وابسته‌اند و تضمینی برای قیمت معامله یا بازده
            سرمایه‌گذاری نیستند. استفاده از ابزارها نیازمند ورود و دسترسی مجاز است.
          </p>
        </section>

        <LandingPlans />
        {dashboard && <DashboardAccess />}
        <section id="agency-services" className="landing-container landing-partners" aria-labelledby="partners-heading">
          <div className="landing-partner-mark" aria-hidden="true">
            <IconBuildingCommunity size={42} stroke={1.2} />
          </div>
          <div>
            <p className="landing-kicker">برای مشاوران و آژانس‌ها</p>
            <h2 id="partners-heading">نگاه مشترک به بازار، همکاری حرفه‌ای‌تر</h2>
            <p>ثبت و مدیریت فایل‌های دفتر و ابزارهای همکاری، در کنار تحلیل بازار و ارزش‌گذاری ملک.</p>
          </div>
          <Link className="landing-button landing-button-outline" href={landingRoutes.submit}>
            ثبت و فایلینگ ملک <IconArrowUpLeft aria-hidden size={18} />
          </Link>
        </section>
      </Content>
      <LandingFooter dashboard={dashboard} />
      <div className="landing-grain" aria-hidden="true" />
    </div>
  );
}
