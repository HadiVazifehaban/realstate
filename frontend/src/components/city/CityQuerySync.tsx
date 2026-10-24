'use client';

import * as React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useCityStore } from '@/store/useCityStore';

/**
 * با تغییر شهر فعال شکارچی، فیدهای وابسته به شهر را بی‌اعتبار می‌کند تا
 * لیست آگهی‌ها و پایپ‌لاین‌ها بدون رفرش کامل (SPA) کوئری مجدد بخورند.
 *
 * زیر QueryProvider در providers.tsx سوار می‌شود.
 */
export default function CityQuerySync() {
  const queryClient = useQueryClient();
  const activeCityId = useCityStore((s) => s.activeCity?.id);
  const hasHydrated = useCityStore((s) => s.hasHydrated);
  const firstRun = React.useRef(true);

  React.useEffect(() => {
    if (!hasHydrated) return;
    // تغییر شهر در اولین hydration رفرش نمی‌خواهد — داده‌ها تازه‌اند.
    if (firstRun.current) {
      firstRun.current = false;
      return;
    }
    void queryClient.invalidateQueries({ queryKey: ['properties'] });
    void queryClient.invalidateQueries({ queryKey: ['bargains'] });
    void queryClient.invalidateQueries({ queryKey: ['property'] });
    void queryClient.invalidateQueries({ queryKey: ['network'] });
  }, [activeCityId, hasHydrated, queryClient]);

  return null;
}
