import { buttonVariants } from '@/components/ui/button';
import { CLERK_ENABLED, cn } from '@/lib/utils';
import { SignUp as ClerkSignUpForm } from '@clerk/nextjs';
import { Metadata } from 'next';
import Link from 'next/link';
import { Logo } from '@/components/brand/logo';
import { InteractiveGridPattern } from './interactive-grid';

export const metadata: Metadata = {
  title: "Authentication",
  description: "Authentication forms built using the components."
};

export default function SignUpViewPage() {
  // Clerk's <SignUp> reads Clerk context, which is not mounted under the bypass
  // or under Keycloak -- it throws and 500s the page. Offer a way onward instead.
  if (!CLERK_ENABLED) {
    return (
      <div className='flex min-h-screen flex-col items-center justify-center gap-6 p-4'>
        <div className='flex flex-col items-center gap-3'>
          <Logo size={160} priority />
          <h1 className='text-2xl font-semibold'>ثبت‌نام در شکارچی</h1>
        </div>
        <p className='text-muted-foreground text-center'>
          احراز هویت در حالت توسعه غیرفعال است. برای ورود به داشبورد ادامه دهید.
        </p>
        <Link href='/dashboard' className={cn(buttonVariants())}>
          رفتن به داشبورد
        </Link>
      </div>
    );
  }

  return (
    <div className='relative h-screen flex-col items-center justify-center md:grid lg:max-w-none lg:grid-cols-2 lg:px-0'>
      <Link
        href='/examples/authentication'
        className={cn(
          buttonVariants({ variant: "ghost" }),
          "absolute top-4 end-4 hidden md:top-8 md:end-8"
        )}
      >
        Sign Up
      </Link>
      <div className='relative hidden h-full flex-col p-10 lg:flex dark:border-r'>
        <div className='absolute inset-0 bg-sidebar' />
        <div className='text-sidebar-foreground relative z-20 flex items-center gap-2 text-lg font-medium'>
          <Logo size={36} priority />
          <span>شکارچی</span>
        </div>
        <InteractiveGridPattern
          className={cn(
            "mask-[radial-gradient(400px_circle_at_center,white,transparent)]",
            "inset-x-0 inset-y-[0%] h-full skew-y-12"
          )}
        />
        <div className='text-sidebar-foreground relative z-20 mt-auto'>
          <blockquote className='space-y-2'>
            <p className='text-lg'>
              &ldquo;This starter template has saved me countless hours of work and helped me
              deliver projects to my clients faster than ever before.&rdquo;
            </p>
            <footer className='text-sidebar-foreground/70 text-sm'>Random Dude</footer>
          </blockquote>
        </div>
      </div>
      <div className='flex h-full items-center justify-center p-4 lg:p-8'>
        <div className='flex w-full max-w-md flex-col items-center justify-center space-y-6'>
          <ClerkSignUpForm />
        </div>
      </div>
    </div>
  );
}
