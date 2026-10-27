"use client";

import type { ReactNode, ComponentProps, FormEvent } from "react";
import Link from "next/link";
import { useState } from "react";
import { usePathname } from "next/navigation";
import {
  IconBuilding,
  IconArrowsExchange,
  IconArrowUpLeft,
  IconShare,
  IconUsers,
  IconNetwork,
  IconWallet,
  IconChevronLeft
} from "@tabler/icons-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createWorkspace } from "@/features/network/api/client";
import PageContainer from "@/components/layout/page-container";
import "./network-workspace.css";

const sections = [
  { slug: "agencies", title: "دفاتر همکار", subtitle: "کشف و گسترش ارتباطات", icon: IconBuilding },
  {
    slug: "requests",
    title: "درخواست‌های همکاری",
    subtitle: "شروع یک همکاری تازه",
    icon: IconUsers
  },
  {
    slug: "shared-listings",
    title: "فایل‌های اشتراکی",
    subtitle: "موجودی مشترک شبکه",
    icon: IconShare
  },
  {
    slug: "referrals",
    title: "ارجاع‌ها",
    subtitle: "پیگیری فرصت‌ها تا نتیجه",
    icon: IconArrowUpLeft
  },
  {
    slug: "transfers",
    title: "انتقال فایل‌ها",
    subtitle: "واگذاری مسئولیت فایل",
    icon: IconArrowsExchange
  },
  {
    slug: "commissions",
    title: "کمیسیون و تسویه",
    subtitle: "توافق‌ها، سهم‌ها و پرداخت‌ها",
    icon: IconWallet
  }
];

export function NetworkPage({
  children,
  pageTitle,
  pageDescription,
  ...props
}: ComponentProps<typeof PageContainer>) {
  const pathname = usePathname();
  const current = sections.find((section) =>
    pathname.startsWith(`/dashboard/network/${section.slug}`)
  );
  const Icon = current?.icon ?? IconNetwork;
  return (
    <div className="network-workspace flex min-w-0 flex-1 flex-col" dir="rtl">
      <PageContainer
        {...props}
        pageHeaderAction={
          <Link
            href="/dashboard/network"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary"
          >
            نمای کلی شبکه <IconChevronLeft className="size-3.5" aria-hidden="true" />
          </Link>
        }
      >
        {pathname === "/dashboard/network/agencies" && <WorkspaceRegistrationForm />}
        <header className="network-hero relative mb-5 overflow-hidden rounded-2xl border p-5 sm:p-7">
          <div className="relative flex items-start gap-4">
            <div className="flex size-12 shrink-0 items-center justify-center rounded-2xl border border-primary/15 bg-background/80 text-primary shadow-sm sm:size-14">
              <Icon className="size-6" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <p className="mb-2 flex items-center gap-2 text-xs font-medium text-primary">
                <IconNetwork className="size-3.5" aria-hidden="true" /> شبکه همکاری دفاتر
              </p>
              <h1 className="text-xl font-bold tracking-tight sm:text-2xl">{pageTitle}</h1>
              <p className="mt-2 max-w-2xl text-sm leading-7 text-muted-foreground">
                {pageDescription}
              </p>
            </div>
          </div>
        </header>
        <nav
          aria-label="بخش‌های شبکه همکاری"
          className="mb-6 grid grid-cols-2 gap-2 rounded-2xl border bg-muted/25 p-2 sm:grid-cols-3 xl:grid-cols-6"
        >
          {sections.map((section) => {
            const active = current?.slug === section.slug;
            const SectionIcon = section.icon;
            return (
              <Link
                key={section.slug}
                href={`/dashboard/network/${section.slug}`}
                aria-current={active ? "page" : undefined}
                className={`flex min-w-0 items-center gap-2.5 rounded-xl border px-3 py-3 transition-colors focus-visible:outline-2 focus-visible:outline-primary ${active ? "border-primary/20 bg-background text-primary shadow-sm" : "border-transparent text-muted-foreground hover:bg-background hover:text-foreground"}`}
              >
                <SectionIcon className="size-5 shrink-0" aria-hidden="true" />
                <span className="min-w-0">
                  <span className="block text-xs font-semibold sm:text-sm">{section.title}</span>
                  <span className="mt-1 hidden text-[10px] opacity-75 sm:block">
                    {section.subtitle}
                  </span>
                </span>
              </Link>
            );
          })}
        </nav>
        <div className="network-content min-w-0">{children}</div>
      </PageContainer>
    </div>
  );
}

export function NetworkStats({
  items
}: {
  items: { label: string; value: number; hint?: string }[];
}) {
  return (
    <section
      aria-label="خلاصه موارد بارگذاری‌شده"
      className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4"
    >
      {items.map((item) => (
        <div key={item.label} className="rounded-xl border bg-card p-4">
          <p className="text-xs text-muted-foreground">{item.label}</p>
          <p className="my-2 text-2xl font-bold tabular-nums">
            {item.value.toLocaleString("fa-IR")}
          </p>
          {item.hint && <p className="text-[11px] text-muted-foreground">{item.hint}</p>}
        </div>
      ))}
    </section>
  );
}

export function NetworkToolbar({ children }: { children: ReactNode }) {
  return (
    <div className="mb-5 flex flex-col gap-3 rounded-xl border bg-card p-3 sm:flex-row sm:items-center sm:justify-between">
      {children}
    </div>
  );
}

export function WorkspaceRegistrationForm() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: "", slug: "", referral_code: "" });
  const create = useMutation({
    mutationFn: createWorkspace,
    onSuccess: async () => {
      toast.success("درخواست ثبت دفتر ایجاد شد.");
      setForm({ name: "", slug: "", referral_code: "" });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["workspaces"] }),
        queryClient.invalidateQueries({ queryKey: ["network"] })
      ]);
    },
    onError: (error: Error) => toast.error(error.message)
  });

  return (
    <form
      className="mb-5 grid gap-3 rounded-xl border bg-card p-4 sm:grid-cols-2"
      onSubmit={(event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        create.mutate({
          name: form.name.trim(),
          name_fa: form.name.trim(),
          slug: form.slug.trim().toLowerCase(),
          referral_code: form.referral_code.trim().toUpperCase()
        });
      }}
    >
      <h2 className="sm:col-span-2 text-base font-semibold">ثبت دفتر جدید</h2>
      <Input required minLength={2} maxLength={255} placeholder="نام دفتر" value={form.name}
        onChange={(event) => setForm({ ...form, name: event.target.value })} />
      <Input required minLength={2} maxLength={64} pattern="[a-z0-9-]+" placeholder="شناسه انگلیسی دفتر"
        value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value })} />
      <div className="space-y-1 sm:col-span-2">
        <label htmlFor="workspace-referral-code" className="text-sm font-medium">کد معرف (اختیاری)</label>
        <Input id="workspace-referral-code" autoComplete="off" maxLength={16} placeholder="کد معرف دفتر همکار"
          value={form.referral_code} onChange={(event) => setForm({ ...form, referral_code: event.target.value.toUpperCase() })} />
        <p className="text-xs text-muted-foreground">اگر از طرف یک دفتر همکار معرفی شده‌اید، کد معرف آن دفتر را وارد کنید.</p>
      </div>
      <Button className="sm:col-span-2" type="submit" disabled={create.isPending}>
        {create.isPending ? "در حال ثبت…" : "ثبت دفتر"}
      </Button>
    </form>
  );
}
