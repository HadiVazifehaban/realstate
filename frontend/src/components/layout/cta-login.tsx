'use client';

import { Icons } from '@/components/icons';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useAuthUser } from '@/hooks/use-auth';

export default function CtaLogin() {
  const user = useAuthUser();
  if (user) return null;
  return (
    <Link
      aria-label='ورود / ثبت‌نام'
      href='/auth/sign-in'
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg',
        'px-3 py-1.5 text-sm font-medium',
        'transition-all duration-200',
        'bg-primary text-primary-foreground',
        'hover:bg-primary/90 hover:shadow-sm',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        'flex'
      )}
    >
      <Icons.login className='h-4 w-4' />
      <span>ورود / ثبت‌نام</span>
    </Link>
  );
}
