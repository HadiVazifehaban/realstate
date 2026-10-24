'use client';

import * as React from 'react';
import CitySelectorModal from '@/components/city/CitySelectorModal';
import { useCityStore } from '@/store/useCityStore';
import { usePathname } from 'next/navigation';

/**
 * گیت انتخاب شهر شکارچی — جایگزین RequireCitySelection قدیمی.
 *
 * استیت از Zustand (persist روی `shekarchi_active_city`) خوانده می‌شود؛
 * قبل از hydration چیزی بلاک نمی‌شود تا hydration mismatch رخ ندهد.
 */
export default function RequireCitySelection({ children }: { children: React.ReactNode }) {
  const hasHydrated = useCityStore((s) => s.hasHydrated);
  const pathname = usePathname();

  if (!hasHydrated || pathname === '/access-denied') return <>{children}</>;

  return (
    <>
      {children}
      <CitySelectorModal />
    </>
  );
}

// Re-export برای سازگاری با ایمپورتهای قدیمی.
export { useCityStore, useActiveCityName } from '@/store/useCityStore';
