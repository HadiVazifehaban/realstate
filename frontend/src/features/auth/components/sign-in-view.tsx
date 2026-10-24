"use client";

import { Icons } from '@/components/icons';
import { buttonVariants, Button } from '@/components/ui/button';
import { AUTH_BYPASS_ENABLED, KEYCLOAK_ENABLED, cn } from '@/lib/utils';
import { SignIn as ClerkSignInForm } from '@clerk/nextjs';
import Link from 'next/link';
import { useEffect } from 'react';
import type { ReactNode } from 'react';
import { Logo } from '@/components/brand/logo';
import { AnimatedHeading } from './animated-heading';
import { signIn } from 'next-auth/react';
import { safeInternalPath } from '@/lib/auth/session-validity';

/**
 * The three things the office actually does, in the product's own vocabulary
 * (see `config/nav-config.ts`). They are the login page's only claim about the
 * product, so they are drawn from shipped features rather than invented: AVM
 * pricing, the five-phase deal pipeline and listing management.
 *
 * These are not links. Everything except `/auth/*` sits behind the session, so
 * a link here would bounce the visitor straight back to this page.
 */
const PILLARS = [
  {
    icon: 'building' as const,
    title: 'ثبت و مدیریت آگهی',
    body: 'ملک را یک‌بار ثبت کنید و در همهٔ فرایندهای بعدی به آن ارجاع دهید.'
  },
  {
    icon: 'trendingUp' as const,
    title: 'ارزش‌گذاری AVM',
    body: 'قیمت پیشنهادی را پیش از بازار با داده‌های واقعی بسنجید.'
  },
  {
    icon: 'kanban' as const,
    title: 'پایپ‌لاین پنج‌فاز',
    body: 'مشتری را از تماس تا بستن معامله، مرحله‌به‌مرحله دنبال کنید.'
  }
];

/**
 * The brand half of the split screen.
 *
 * The reference design layers a photograph and a looping video under a vertical
 * gradient. Both are hotlinked from the template vendor's CDN, which would both
 * put another company's imagery on our login page and add a third-party origin
 * to the critical path of a page every user hits signed-out. The depth is
 * rebuilt here from gradients and a line grid instead, in the rose-gold-on-navy
 * palette the property pages already use.
 */
function ShowcasePanel() {
  return (
    <div className='relative hidden min-h-screen flex-col overflow-hidden p-10 lg:flex xl:p-14'>
      <div
        aria-hidden
        className='pointer-events-none absolute inset-0 [background:radial-gradient(70%_55%_at_50%_0%,rgb(229_168_123/0.20),transparent_70%)]'
      />
      <div
        aria-hidden
        className='pointer-events-none absolute inset-x-0 top-0 h-[70%] [background:linear-gradient(to_bottom,rgb(184_124_79/0.20),transparent_65%)]'
      />
      <div
        aria-hidden
        className='showcase-grid pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,black,transparent_78%)]'
      />

      <div className='relative z-10 flex items-center justify-between'>
        <Link
          href='/'
          className='flex items-center gap-3 rounded-lg focus-visible:ring-2 focus-visible:ring-gold-accent/50 focus-visible:outline-none'
        >
          {/* The mark is a circular coin with transparent corners — it sits on
              this dark panel with no chip behind it. */}
          <Logo size={40} priority />
          <span className='text-showcase-text text-lg font-semibold'>شکارچی</span>
        </Link>
        <span className='showcase-pill text-showcase-muted text-xs'>
          <Icons.lock aria-hidden className='h-3.5 w-3.5' />
          محیط امن
        </span>
      </div>

      <div className='relative z-10 my-auto max-w-2xl py-14 text-center'>
        <span className='showcase-pill text-showcase-muted text-xs'>
          <Icons.sparkles aria-hidden className='h-3.5 w-3.5 text-gold-accent' />
          سامانهٔ مدیریت املاک
        </span>

        <h1 className='text-showcase-text mt-8 text-4xl leading-[1.35] font-bold tracking-tight xl:text-5xl'>
          <AnimatedHeading text='ملک‌ها، قیمت‌ها و معاملات در یک جا' />
        </h1>

        <p className='text-showcase-muted mx-auto mt-6 max-w-lg text-base leading-8'>
          آگهی را ثبت کنید، قیمت را با ارزش‌گذاری AVM بسنجید و مشتری را در
          پایپ‌لاین پنج‌فاز تا بستن معامله دنبال کنید.
        </p>
      </div>

      <ul className='relative z-10 grid grid-cols-3 gap-6 border-t border-showcase-border pt-8'>
        {PILLARS.map(({ icon, title, body }) => {
          const Icon = Icons[icon];
          return (
            <li key={title} className='space-y-2'>
              <span className='text-gold-accent border-showcase-border bg-white/5 inline-flex h-9 w-9 items-center justify-center rounded-xl border'>
                <Icon aria-hidden className='h-4 w-4' />
              </span>
              <p className='text-showcase-text text-sm font-medium'>{title}</p>
              <p className='text-showcase-dim text-xs leading-6'>{body}</p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/**
 * The credential half. `children` is the mode-specific control: the Keycloak
 * hand-off, the local-dev bypass link, or Clerk's own form.
 */
function AuthPanel({ children }: { children: ReactNode }) {
  return (
    <div className='relative flex min-h-screen items-center justify-center px-6 py-24 lg:py-10'>
      <div className='absolute inset-x-0 top-0 flex items-center gap-2.5 px-6 py-6 lg:hidden'>
        <Logo size={34} priority />
        <span className='text-showcase-text font-semibold'>شکارچی</span>
      </div>

      <div className='showcase-panel w-full max-w-md p-8 sm:p-10'>
        <span className='from-gold-primary to-gold-dark shadow-gold-accent/25 mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-linear-to-br text-showcase shadow-lg'>
          <Icons.lock aria-hidden className='h-6 w-6' />
        </span>

        <h2 className='text-showcase-text mt-6 text-center text-2xl font-semibold'>
          ورود به شکارچی
        </h2>
        <p className='text-showcase-muted mt-2 text-center text-sm leading-6'>
          برای دسترسی به آگهی‌ها، ارزش‌گذاری و پیگیری معاملات وارد شوید.
        </p>

        <div className='mt-8'>{children}</div>

        {/* Self-service registration is disabled on the realm, so the reference
            design's "need an account? sign up" footer would be a dead end.
            Say where accounts come from instead. */}
        <p className='text-showcase-dim mt-8 flex items-start gap-2 border-t border-showcase-border pt-6 text-xs leading-5'>
          <Icons.info aria-hidden className='mt-0.5 h-4 w-4 shrink-0' />
          <span>
            حساب کاربری توسط مدیر دفتر صادر می‌شود. اگر حساب ندارید با پشتیبانی
            تماس بگیرید.
          </span>
        </p>
      </div>
    </div>
  );
}

export default function SignInViewPage() {
  // Keycloak mode: redirect directly to the realm's login page so users
  // land on the themed Keycloak surface immediately (no intermediate form).
  if (KEYCLOAK_ENABLED) {
    useEffect(() => {
      const callbackUrl = safeInternalPath(
        new URLSearchParams(window.location.search).get('callbackUrl')
      ) ?? '/dashboard/properties';
      signIn('keycloak', { callbackUrl });
    }, []);

return (
      <div className='flex min-h-screen items-center justify-center'>
        <div className='animate-pulse flex items-center gap-3 text-showcase-muted'>
          <Icons.spinner className='h-6 w-6' />
          <span>در حال انتقال به صفحهٔ ورود…</span>
        </div>
      </div>
    );
  }

  // Clerk's <SignIn> reads Clerk context, which the local-dev bypass does not
  // mount -- it throws and 500s the page. Offer a way onward instead.
  if (AUTH_BYPASS_ENABLED) {
    return (
      <div className='showcase-shell grid min-h-screen lg:grid-cols-2'>
        <AuthPanel>
          <div className='space-y-4 text-center'>
            <p className='text-showcase-muted text-sm leading-6'>
              احراز هویت در حالت توسعه غیرفعال است. برای ورود به داشبورد ادامه
              دهید.
            </p>
            <Link
              href='/dashboard/properties'
              className={cn(
                buttonVariants(),
                'from-gold-primary to-gold-dark text-showcase h-12 w-full rounded-xl bg-linear-to-l'
              )}
            >
              رفتن به داشبورد
            </Link>
          </div>
        </AuthPanel>
        <ShowcasePanel />
      </div>
    );
  }

  // Clerk renders its own light-themed form, so it keeps the dashboard's theme
  // rather than being dropped into the dark showcase card. ShowcasePanel is
  // already `hidden lg:flex`, so it is a plain grid child here.
  return (
    <div className='grid min-h-screen lg:grid-cols-2'>
      <div className='flex min-h-screen items-center justify-center p-4 lg:p-8'>
        <div className='w-full max-w-md'>
          <ClerkSignInForm />
          <div className='mt-6 space-y-3'>
            <hr className='border-t border-slate-200' />
            <p className='text-xs text-slate-500 text-center'>یا وارد شوید با</p>
            <Button type='button' className='w-full' onClick={() => { window.location.href = '/auth/sign-up'; }}>
              ورود با کد موبایل (یک‌بارصرف)
            </Button>
          </div>
        </div>
      </div>
      <ShowcasePanel />
    </div>
  );
}
