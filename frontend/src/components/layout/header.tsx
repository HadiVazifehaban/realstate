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

export default function Header() {
  return (
    <header className="dashboard-top-header" dir="rtl">
      <div className="dashboard-header-primary">
        <LandingBrand dashboard header />
        <DashboardTopNav />
        <div className="dashboard-header-utilities">
          <OrgSwitcher />
          <Link className="dashboard-submit" href="/dashboard/properties/submit">
            <Icons.plusCircle size={18} aria-hidden /> <span>ثبت ملک</span>
          </Link>
          <ThemeModeToggle />
          <CtaLogin />
          <UserNav />
        </div>
      </div>
    </header>
  );
}
