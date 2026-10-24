import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { AUTH_BYPASS_ENABLED, KEYCLOAK_ENABLED } from "@/lib/utils";
import { LandingPage } from "@/features/landing/components/landing-page";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "شکارچی — خانهٔ سامانه",
  description: "تحلیل بازار و مدیریت املاک ایران؛ دسترسی به ابزارهای مجاز حساب شما."
};

export default async function Dashboard() {
  // Under the local-dev bypass there is no Clerk session and clerkMiddleware()
  // never runs, so `auth()` throws instead of returning null. Skip the check and
  // render the dashboard home directly. See AUTH_BYPASS_ENABLED in lib/utils.
  if (AUTH_BYPASS_ENABLED) {
    return <LandingPage dashboard />;
  }

  // Same story under Keycloak: no Clerk session exists, so `auth()` would throw.
  // proxy.ts already gates /dashboard on the Auth.js session.
  if (KEYCLOAK_ENABLED) {
    return <LandingPage dashboard />;
  }

  const { userId } = await auth();

  if (!userId) {
    return redirect("/auth/sign-in");
  } else {
    return <LandingPage dashboard />;
  }
}
