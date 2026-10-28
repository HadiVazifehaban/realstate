import React from "react";
import Link from "next/link";
import { Icons } from "@/components/icons";
import { LandingBrand } from "@/features/landing/components/brand";
import { DashboardTopNav } from "@/features/landing/components/dashboard-top-nav";
import { OrgSwitcher } from "../org-switcher";
import "./dashboard-header.css";
import { ThemeModeToggle } from "../themes/theme-mode-toggle";
import CtaLogin from "./cta-login";
import { UserNav } from "./user-nav";
import HeaderLocationPicker from "./header-location-picker";

export default function Header() {
  return (
    <header className="dashboard-top-header" dir="rtl">
      <div className="dashboard-header-primary">
        <LandingBrand dashboard header />
        <div className="hidden min-[1600px]:block">
          <DashboardTopNav />
        </div>
        <details className="dashboard-mobile-menu">
          <summary aria-label="بازکردن منوی اصلی">
            <Icons.menu aria-hidden />
          </summary>
          <div className="dashboard-mobile-menu-panel">
            <DashboardTopNav ariaLabel="ناوبری موبایل" />
          </div>
        </details>
        <div className="dashboard-header-utilities">
          <div className="hidden md:block">
            <OrgSwitcher />
          </div>
          <div className="dashboard-header-city-picker hidden md:block">
            <HeaderLocationPicker />
          </div>
          <Link
            className="dashboard-submit hidden md:inline-flex"
            href="/dashboard/properties/submit"
          >
            <Icons.plusCircle size={18} aria-hidden /> <span>ثبت ملک</span>
          </Link>
          <div className="dashboard-header-theme hidden md:block">
            <ThemeModeToggle />
          </div>
          <div className="dashboard-header-login">
            <CtaLogin />
          </div>
          <UserNav />
        </div>
      </div>
    </header>
  );
}
