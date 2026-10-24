'use client';

import * as React from 'react';
import { Icons } from '@/components/icons';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { POPULAR_CITIES, SHEKARCHI_CITIES, type ShekarchiCity } from '@/constants/cities';
import { useCityStore } from '@/store/useCityStore';

function normalizeSearch(input: string): string {
  return input.toLowerCase().replace(/[يى]/g, 'ی').replace(/ك/g, 'ک').replace(/[\s‌ـ]/g, '').trim();
}

export default function CitySelectorModal() {
  const activeCity = useCityStore((s) => s.activeCity);
  const isOpen = useCityStore((s) => s.isCityModalOpen);
  const initialGate = useCityStore((s) => s.initialGate);
  const setActiveCity = useCityStore((s) => s.setActiveCity);
  const closeCityModal = useCityStore((s) => s.closeCityModal);
  const [query, setQuery] = React.useState('');
  const [showAll, setShowAll] = React.useState(false);

  React.useEffect(() => {
    if (isOpen) { setQuery(''); setShowAll(false); }
  }, [isOpen]);

  React.useEffect(() => {
    if (!isOpen || initialGate) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') closeCityModal(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, initialGate, closeCityModal]);

  const filtered = React.useMemo(() => {
    const q = normalizeSearch(query);
    if (!q) return SHEKARCHI_CITIES;
    return SHEKARCHI_CITIES.filter((c) => normalizeSearch(c.name).includes(q) || normalizeSearch(c.province).includes(q));
  }, [query]);

  if (!isOpen) return null;

  const popular = query.trim() || showAll ? [] : POPULAR_CITIES;
  const rest = query.trim() ? filtered : showAll ? SHEKARCHI_CITIES : SHEKARCHI_CITIES.filter((c) => !c.isPopular);

  const btn = (city: ShekarchiCity) => {
    const on = activeCity?.id === city.id;
    return (
      <button key={city.id} type='button' onClick={() => setActiveCity(city)}
        className={cn('group flex w-full items-center justify-between gap-2 rounded-xl border px-3 py-2.5 text-right transition-all duration-200',
          on ? 'border-[#e5a87b]/70 bg-[#e5a87b]/15 shadow-[0_2px_16px_rgba(229,168,123,0.25)]'
            : 'border-[#ffd8be]/20 bg-white/[0.03] hover:border-[#e5a87b]/50 hover:bg-[#e5a87b]/10')}>
        <span className='flex items-center gap-2.5'>
          <Icons.mapPin className={cn('size-4 shrink-0', on ? 'text-[#e5a87b]' : 'text-[#ffd8be]/60 group-hover:text-[#e5a87b]')} aria-hidden />
          <span>
            <span className='block text-sm font-semibold text-white'>{city.name}</span>
            <span className='block text-[11px] text-gray-400'>{city.province}</span>
          </span>
        </span>
        {on && <Icons.check className='size-4 shrink-0 text-[#e5a87b]' aria-hidden />}
      </button>
    );
  };

  return (
    <div className='fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-xl'
      onClick={() => { if (!initialGate) closeCityModal(); }} role='dialog' aria-modal='true' aria-label='انتخاب شهر فعالیت شکارچی'>
      <div className='animate-in fade-in zoom-in-95 w-full max-w-md rounded-2xl border border-[#ffd8be]/20 bg-[#060b13] p-6'
        onClick={(e) => e.stopPropagation()}>
        <div className='mb-1 flex items-center justify-between gap-2'>
          <h2 className='flex items-center gap-2 text-base font-bold text-white'>
            <Icons.mapPin className='size-5 text-[#e5a87b]' aria-hidden />
            {initialGate ? 'شهر فعالیت خود را انتخاب کنید' : 'تغییر شهر فعالیت'}
          </h2>
          {!initialGate && (
            <button type='button' onClick={closeCityModal} aria-label='بستن'
              className='rounded-lg p-1.5 text-gray-400 hover:bg-white/10 hover:text-white'>✕</button>
          )}
        </div>
        <p className='mb-4 text-xs leading-relaxed text-gray-400'>
          شکارچی آگهی‌ها، تحلیل‌ها و نقشه را بر اساس همین شهر به شما نشان می‌دهد.
        </p>
        <div className='relative mb-4'>
          <Icons.search className='pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-[#ffd8be]/50' aria-hidden />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder='جست‌وجوی شهر یا استان…'
            aria-label='جست‌وجوی شهر یا استان'
            className='border-[#ffd8be]/20 bg-white/[0.04] pr-9 text-white placeholder:text-gray-500 focus-visible:border-[#e5a87b]' />
        </div>
        <div className='max-h-72 space-y-2 overflow-y-auto pl-1'>
          {popular.length > 0 && (
            <div className='space-y-2'>
              <p className='text-[11px] font-semibold text-[#ffd8be]/80'>شهرهای پرطرفدار</p>
              {popular.map(btn)}
              <p className='pt-1 text-[11px] font-semibold text-[#ffd8be]/80'>سایر شهرها</p>
            </div>
          )}
          {rest.map(btn)}
          {filtered.length === 0 && <p className='py-6 text-center text-sm text-gray-400'>شهری با این نام پیدا نشد.</p>}
        </div>
        {!query.trim() && !showAll && (
          <button type='button' onClick={() => setShowAll(true)}
            className='mt-3 w-full rounded-xl border border-[#ffd8be]/20 py-2 text-xs font-semibold text-[#ffd8be] hover:border-[#e5a87b]/50 hover:bg-[#e5a87b]/10'>
            نمایش همهٔ شهرها
          </button>
        )}
      </div>
    </div>
  );
}
