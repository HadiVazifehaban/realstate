"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { IconMenu2, IconX, IconArrowUpLeft, IconShieldLock } from "@tabler/icons-react";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger
} from "@/components/ui/dialog";
import { LandingBrand } from "./brand";
import { DashboardTopNav } from "./dashboard-top-nav";
import { UserNav } from "@/components/layout/user-nav";
import { ThemeModeToggle } from "@/components/themes/theme-mode-toggle";
import { landingRoutes, publicNavigation } from "../config";

export function LandingHeader({ dashboard = false }: { dashboard?: boolean }) {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => {
    const update = () => setScrolled(window.scrollY > 24);
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, []);

  return (
    <header className={`landing-header ${scrolled ? "is-scrolled" : ""}`}>
      <div className="landing-header-inner">
        <LandingBrand dashboard={dashboard} />
        {dashboard ? (
          <DashboardTopNav />
        ) : (
          <nav aria-label="ناوبری اصلی" className="landing-desktop-nav">
            {publicNavigation.map((item) => (
              <Link key={item.href} href={item.href}>
                {item.label}
              </Link>
            ))}
          </nav>
        )}
        <div className="landing-header-actions">
          <ThemeModeToggle />
          {dashboard ? (
            <UserNav placement="landing" />
          ) : (
            <Dialog>
              <DialogTrigger className="landing-button landing-button-quiet">
                ورود / ثبت‌نام
              </DialogTrigger>
              <DialogContent dir="rtl" showCloseButton={false} className="landing-auth-dialog">
                <DialogClose className="landing-dialog-close" aria-label="بستن پنجرهٔ ورود">
                  <IconX aria-hidden size={20} />
                </DialogClose>
                <IconShieldLock aria-hidden className="landing-dialog-icon" size={36} />
                <DialogTitle className="landing-dialog-title">به شکارچی خوش آمدید</DialogTitle>
                <DialogDescription className="landing-dialog-description">
                  برای استفاده از تحلیل بازار و ابزارهای حرفه‌ای، وارد حساب خود شوید یا مراحل ثبت‌نام
                  را آغاز کنید.
                </DialogDescription>
                <Link className="landing-button landing-button-primary" href={landingRoutes.signIn}>
                  ورود به حساب <IconArrowUpLeft aria-hidden size={18} />
                </Link>
                <Link className="landing-button landing-button-outline" href={landingRoutes.signUp}>
                  ایجاد حساب کاربری
                </Link>
                <p className="landing-dialog-note">
                  دسترسی به ابزارها مطابق نقش و وضعیت تأیید حساب شما تعیین می‌شود.
                </p>
              </DialogContent>
            </Dialog>
          )}
          <Link
            className="landing-button landing-button-outline landing-submit"
            href={landingRoutes.submit}
          >
            ثبت ملک <span aria-hidden>＋</span>
          </Link>
          {!dashboard && (
            <Dialog open={menuOpen} onOpenChange={setMenuOpen}>
              <DialogTrigger className="landing-menu-trigger" aria-label="بازکردن منوی اصلی">
                <IconMenu2 aria-hidden size={23} />
              </DialogTrigger>
              <DialogContent
                dir="rtl"
                showCloseButton={false}
                className="landing-auth-dialog landing-mobile-dialog"
              >
                <DialogClose className="landing-dialog-close" aria-label="بستن منوی اصلی">
                  <IconX aria-hidden size={22} />
                </DialogClose>
                <DialogTitle className="landing-dialog-title">کاوش در شکارچی</DialogTitle>
                <DialogDescription className="landing-dialog-description">
                  ابزارهای تحلیل بازار و حساب کاربری
                </DialogDescription>
                <nav aria-label="ناوبری موبایل" className="landing-mobile-nav">
                  {publicNavigation.map((item) => (
                    <Link key={item.href} href={item.href} onClick={() => setMenuOpen(false)}>
                      {item.label}
                      <IconArrowUpLeft size={17} aria-hidden />
                    </Link>
                  ))}
                  <Link href={landingRoutes.submit} onClick={() => setMenuOpen(false)}>
                    ثبت ملک
                    <IconArrowUpLeft size={17} aria-hidden />
                  </Link>
                  <Link href={landingRoutes.signUp} onClick={() => setMenuOpen(false)}>
                    ثبت‌نام
                    <IconArrowUpLeft size={17} aria-hidden />
                  </Link>
                </nav>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>
    </header>
  );
}
