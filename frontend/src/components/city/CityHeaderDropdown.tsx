'use client';

import { Icons } from '@/components/icons';
import { useCityStore } from '@/store/useCityStore';

/** دکمهٔ «📍 شهر ▾» تاپ‌بار شکارچی — بازکنندهٔ سوییچر شهر. */
export default function CityHeaderDropdown() {
  const activeCity = useCityStore((s) => s.activeCity);
  const hasHydrated = useCityStore((s) => s.hasHydrated);
  const openCityModal = useCityStore((s) => s.openCityModal);

  return (
    <button type='button' onClick={() => openCityModal(false)}
      aria-label='تغییر شهر فعالیت'
      className='flex h-9 items-center gap-1.5 rounded-full border border-[#ffd8be]/25 bg-[#e5a87b]/10 px-3 text-xs font-semibold text-[#ffd8be] transition-all duration-200 hover:border-[#e5a87b]/60 hover:bg-[#e5a87b]/20'>
      <Icons.mapPin className='size-3.5' aria-hidden />
      <span>{hasHydrated ? (activeCity?.name ?? 'انتخاب شهر') : '…'}</span>
      <Icons.chevronDown className='size-3.5 opacity-70' aria-hidden />
    </button>
  );
}
