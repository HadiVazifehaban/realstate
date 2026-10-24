import { auth } from '@clerk/nextjs/server';
import { redirect } from 'next/navigation';
import { AUTH_BYPASS_ENABLED, KEYCLOAK_ENABLED } from '@/lib/utils';

export default async function Dashboard() {
  // Under the local-dev bypass there is no Clerk session and clerkMiddleware()
  // never runs, so `auth()` throws instead of returning null. Skip the check and
  // land on the overview directly. See AUTH_BYPASS_ENABLED in lib/utils.
  if (AUTH_BYPASS_ENABLED) {
    redirect("/dashboard/overview");
  }

  // Same story under Keycloak: no Clerk session exists, so `auth()` would throw.
  // proxy.ts already gates /dashboard on the Auth.js session.
  if (KEYCLOAK_ENABLED) {
    redirect("/dashboard/properties");
  }

  const { userId } = await auth();

  if (!userId) {
    return redirect("/auth/sign-in");
  } else {
    redirect("/dashboard/overview");
  }
}
