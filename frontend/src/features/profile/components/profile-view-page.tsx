"use client";

import { UserProfile } from '@clerk/nextjs';
import { CLERK_ENABLED } from '@/lib/utils';

export default function ProfileViewPage() {
  // Keycloak owns passwords and enforces the realm password policy. The
  // Account Console uses the existing SSO session after SMS or password login.
  if (!CLERK_ENABLED) {
    const issuer = process.env.NEXT_PUBLIC_KEYCLOAK_ISSUER?.replace(/\/$/, '');
    return (
      <div className='flex w-full flex-col gap-4 p-4' dir='rtl'>
        <h1 className='text-xl font-semibold'>امنیت حساب</h1>
        <p>پس از ورود با پیامک، رمز عبور قبلی شما حفظ می‌شود. برای تعریف یا تغییر رمز، از تنظیمات امن حساب Keycloak استفاده کنید.</p>
        {issuer && (
          <a className='inline-flex w-fit rounded-lg bg-primary px-4 py-2 text-primary-foreground' href={`${issuer}/account/#/security/signingin`}>
            مدیریت رمز عبور در Keycloak
          </a>
        )}
      </div>
    );
  }

  return (
    <div className='flex w-full flex-col p-4'>
      <UserProfile />
    </div>
  );
}
