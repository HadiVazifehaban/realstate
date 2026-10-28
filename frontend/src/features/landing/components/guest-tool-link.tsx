"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";
import type { ReactNode } from "react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

interface GuestToolLinkProps {
  href: string;
  children: ReactNode;
  className?: string;
}

export function GuestToolLink({ href, children, className }: GuestToolLinkProps) {
  const { status } = useSession();
  const authenticated = status === "authenticated";

  if (authenticated) {
    return <Link href={href} className={className}>{children}</Link>;
  }

  return (
    <Dialog>
      <DialogTrigger nativeButton={false} render={<Link href={href} className={className} />}>{children}</DialogTrigger>
      <DialogContent dir="rtl" className="border-[var(--brand-ffd8be33)] bg-[var(--brand-111d29)] text-[var(--brand-fff4ec)]">
        <DialogHeader>
          <DialogTitle>برای استفاده از این قابلیت وارد شکارچی شوید</DialogTitle>
          <DialogDescription className="text-[var(--brand-cbd5e1)]">
            با ورود یا عضویت در شکارچی می‌توانید از امکانات اختصاصی این بخش استفاده کنید.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Link
            href={`/auth/sign-in?callbackUrl=${encodeURIComponent(href.startsWith("/") && !href.startsWith("//") ? href : "/")}`}
            className="inline-flex h-10 items-center justify-center rounded-lg bg-[var(--brand-c59b27)] px-4 text-sm font-semibold text-[#11151c]"
          >
            ورود / عضویت
          </Link>
          <DialogTrigger className="inline-flex h-10 items-center justify-center rounded-lg border border-white/15 px-4 text-sm">
            انصراف
          </DialogTrigger>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
