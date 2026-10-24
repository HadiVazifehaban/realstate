"use client";

import { useRouter } from "next/navigation";
import { Icons } from "@/components/icons";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthContext, useAuthSignOut } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";
import { useEffect } from "react";

/**
 * The approval gate.
 *
 * Keycloak issues the token, but a PENDING identity must not see the desk: the
 * FastAPI core rejects such a token with 403 regardless of role, so this screen
 * exists to explain *why* rather than to enforce anything. Reloading re-reads
 * the token, which is how a user picks up their approval without signing in
 * again.
 */
export default function AwaitingApprovalPage() {
  const { kycStatus, isApproved, user, isLoading } = useAuthContext();
  const signOut = useAuthSignOut();
  const router = useRouter();

  // Redirect to dashboard if approved
  useEffect(() => {
    if (isApproved && !isLoading) {
      router.push("/dashboard");
    }
  }, [isApproved, isLoading, router]);

  if (isLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center p-4">
        <div className="text-center">
          <Icons.spinner className="animate-spin mx-auto size-8 mb-4" />
          <p className="text-muted-foreground">در حال بررسی وضعیت...</p>
        </div>
      </main>
    );
  }

  if (isApproved) {
    return (
      <main className="flex min-h-screen items-center justify-center p-4">
        <Card className="max-w-md text-center">
          <CardHeader>
            <CardTitle>حساب شما تأیید شده است</CardTitle>
            <CardDescription>در حال انتقال به داشبورد...</CardDescription>
          </CardHeader>
          <CardContent>
            <Icons.spinner className="animate-spin mx-auto size-8" />
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <div
        className={cn(
          "max-w-md w-full space-y-6 rounded-2xl border border-amber-500/30",
          "bg-slate-900/60 p-8 text-center backdrop-blur"
        )}
      >
        <div className="bg-amber-500/10 border-amber-500/30 mx-auto flex size-16 items-center justify-center rounded-full border">
          <Icons.warning className="text-amber-400 size-8 animate-pulse" />
        </div>

        <div className="space-y-2">
          <h1 className="text-xl font-bold text-slate-100">حساب کاربری در انتظار تأیید امنیتی</h1>
          <p className="text-muted-foreground text-xs leading-relaxed">
            اطلاعات هویتی و مجوز کسب شما ثبت شده است. به منظور حفظ امنیت حریم خصوصی مالکان و داده‌های
            PII، دسترسی به پنل پس از تأیید واحد ممیزی فعال می‌شود.
          </p>
        </div>

        <dl className="bg-slate-900/60 rounded-xl border p-3.5 text-right">
          <Row label="وضعیت در سامانه هویتی" value={kycStatus} highlight />
          <Row label="مرجع تأیید" value="واحد ممیزی و امنیت شکارچی" />
          {user?.emailAddresses?.[0] ? (
            <Row label="حساب" value={user.emailAddresses[0].emailAddress} />
          ) : null}
        </dl>

        <div className="flex gap-3">
          <Button className="flex-1" variant="outline" onClick={() => window.location.reload()}>
            <Icons.spinner />
            بررسی مجدد وضعیت
          </Button>
          <Button variant="ghost" onClick={() => signOut({ redirectUrl: "/auth/sign-in" })}>
            <Icons.logout />
            خروج
          </Button>
        </div>
      </div>
    </main>
  );
}

function Row({
  label,
  value,
  highlight = false
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="flex justify-between text-xs">
      <dt className="text-muted-foreground">{label}:</dt>
      <dd className={cn(highlight && "text-amber-400 font-medium")}>{value}</dd>
    </div>
  );
}
