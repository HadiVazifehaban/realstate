import Link from "next/link";
import { IconArrowUpLeft, IconShieldCheck, IconBuildingCommunity } from "@tabler/icons-react";
import { LandingBrand } from "./brand";
import { landingRoutes, publicNavigation } from "../config";
import { FooterSocialLinks } from "@/features/social-links/footer-social-links";

export function LandingFooter({ dashboard = false }: { dashboard?: boolean }) {
  return (
    <footer id="footer" className="landing-footer bg-background/80 border-t border-primary/15">
      <div className="landing-container">
        <div className="landing-footer-top">
          <div className="landing-footer-about">
            <LandingBrand dashboard={dashboard} />
            <FooterSocialLinks />
            <p>
              شکارچی، سامانهٔ هوشمند تحلیل بازار و شکار فرصت‌های ملکی ایران برای مشاوران حرفه‌ای،
              آژانس‌های املاک و سرمایه‌گذاران.
            </p>
            <Link href="#search" className="landing-footer-brand-link">
              کاوش در بازار املاک <IconArrowUpLeft aria-hidden size={16} />
            </Link>
          </div>
          <nav aria-labelledby="landing-footer-links">
            <h3 id="landing-footer-links">دسترسی سریع</h3>
            {publicNavigation.map((item) => (
              <Link key={item.href} href={item.href}>
                {item.label}
              </Link>
            ))}
          </nav>
          <nav aria-labelledby="landing-footer-services">
            <h3 id="landing-footer-services">خدمات شکارچی</h3>
            <Link href={landingRoutes.submit}>ثبت و فایلینگ ملک</Link>
            {dashboard ? (
              <Link href="/dashboard/profile">پروفایل حساب</Link>
            ) : (
              <>
                <Link href={landingRoutes.signIn + "?callbackUrl=%2Fdashboard"}>ورود به حساب</Link>
                <Link href={landingRoutes.signUp}>ثبت‌نام</Link>
              </>
            )}
            <Link href={landingRoutes.avm}>مشاهدهٔ تحلیل بازار</Link>
            <Link href={landingRoutes.billing}>اشتراک و صورتحساب</Link>
          </nav>
          <div className="landing-footer-contact">
            <h3>همراه مجموعهٔ شما</h3>
            <p>
              ابزارهای تحلیل بازار، مدیریت فایل‌های دفتر و همکاری حرفه‌ای را در حساب شکارچی خود در
              دسترس داشته باشید.
            </p>
            <Link className="landing-button landing-button-outline" href={landingRoutes.dashboard}>
              <IconBuildingCommunity aria-hidden size={17} />
              ورود به سامانه
            </Link>
            <a
              href="https://trustseal.enamad.ir/?id=8391402&Code=K0T3NOuAAuQQo4lxd5jstn0zeSJpPSbT"
              target="_blank"
              rel="noopener noreferrer"
              referrerPolicy="origin"
              aria-label="نماد اعتماد الکترونیکی شکارچی"
              className="mt-4 inline-flex w-fit rounded-xl border border-primary/15 bg-background/40 p-2 transition-colors hover:border-primary/35"
            >
              <img
                src="https://trustseal.enamad.ir/logo.aspx?id=8391402&Code=K0T3NOuAAuQQo4lxd5jstn0zeSJpPSbT"
                alt="نماد اعتماد الکترونیکی"
                width={120}
                height={120}
                loading="lazy"
                referrerPolicy="origin"
                className="h-[100px] w-[100px] object-contain"
              />
            </a>
            <p className="landing-footer-coverage">
              پوشش تحلیل و نقشه به داده‌های موجود هر شهر و محله وابسته است.
            </p>
          </div>
        </div>
        <div className="landing-footer-bottom">
          <p>
            ©{" "}
            {new Intl.DateTimeFormat("fa-IR", { year: "numeric", calendar: "persian" }).format(
              new Date()
            )}{" "}
            شکارچی (SHEKARCHI). تمامی حقوق محفوظ است. طراحی و توسعه:{" "}
            <a
              href="https://ojfarda.ir"
              target="_blank"
              rel="noopener noreferrer"
              className="landing-footer-developer"
            >
              چشم‌انداز اوج فردا (AVG Tech)
            </a>
          </p>
          <span className="landing-footer-payment">
            <IconShieldCheck size={18} aria-hidden />
            پرداخت کارت‌به‌کارت با تأیید مالی{" "}
            <small lang="en" dir="ltr">
              CARD TO CARD
            </small>
          </span>
        </div>
      </div>
    </footer>
  );
}
