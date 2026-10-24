'use client';

import * as React from 'react';
import Link from 'next/link';

import { Icons } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Skeleton } from '@/components/ui/skeleton';
import { useProperties } from '@/features/properties/hooks';
import { DEAL_TYPE_LABELS, PROPERTY_TYPE_LABELS, SOURCE_SHORT_LABELS } from '@/features/properties/utils/labels';
import type { PropertySummary } from '@/features/properties/types';
import { cn, toPersianDigits } from '@/lib/utils';

type DeskTab = 'all' | 'mine' | 'exclusive' | 'radar' | 'stale';

const formatNumber = (value: number | null) =>
  value === null ? '---' : `${toPersianDigits(value.toLocaleString('en-US'))} تومان`;

function staleMeta(property: PropertySummary) {
  if (!property.updated_at) return { label: 'نیازمند بررسی', className: 'border-rose-500/20 bg-rose-500/10 text-rose-400' };
  const hours = Math.max(0, (Date.now() - new Date(property.updated_at).getTime()) / 3_600_000);
  if (hours <= 72) return { label: `${toPersianDigits(String(Math.ceil(hours)))}س`, className: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400' };
  if (hours <= 168) return { label: `${toPersianDigits(String(Math.ceil(hours / 24)))}روز`, className: 'border-amber-500/20 bg-amber-500/10 text-amber-400' };
  return { label: `${toPersianDigits(String(Math.ceil(hours / 24)))}روز`, className: 'animate-pulse border-rose-500/20 bg-rose-500/10 text-rose-400' };
}

function PortfolioRow({ property, onSelect }: { property: PropertySummary; onSelect: (property: PropertySummary) => void }) {
  const freshness = staleMeta(property);
  const isBargain = property.valuation_status === 'BARGAIN';
  return (
    <tr className='border-b border-[#ffd8be]/10 bg-[#0c1424]/60 transition-colors hover:bg-[#121c32]/80'>
      <td className='px-3 py-3'><input aria-label={`انتخاب ${property.title}`} type='checkbox' className='accent-[#e5a87b]' /></td>
      <td className='whitespace-nowrap px-3 py-3 font-mono text-xs text-[#ffd8be]'>#{property.source_ref ?? property.id.slice(0, 8).toUpperCase()}</td>
      <td className='min-w-56 px-3 py-3'>
        <p className='truncate text-sm font-semibold'>{property.title}</p>
        <p className='mt-1 text-xs text-muted-foreground'>{PROPERTY_TYPE_LABELS[property.property_type]} · {DEAL_TYPE_LABELS[property.deal_type]}</p>
      </td>
      <td className='whitespace-nowrap px-3 py-3 text-sm'>{property.city || '---'}<span className='text-muted-foreground'>، {property.neighborhood || '---'}</span></td>
      <td className='whitespace-nowrap px-3 py-3 text-sm'>{property.area ? `${toPersianDigits(property.area.toLocaleString('en-US'))}م` : '---'} / {property.rooms ?? '---'}</td>
      <td className='whitespace-nowrap px-3 py-3 text-sm font-semibold tabular-nums'>{formatNumber(property.total_price)}</td>
      <td className='px-3 py-3'>
        <span className={cn('inline-flex whitespace-nowrap rounded-full border px-2 py-0.5 font-mono text-xs font-semibold', isBargain ? 'border-[#ffd8be]/25 bg-[#ffd8be]/10 text-[#ffd8be]' : 'border-border bg-muted/40 text-muted-foreground')}>
          {property.valuation_deviation_pct !== null ? `${property.valuation_deviation_pct > 0 ? '+' : ''}${toPersianDigits(property.valuation_deviation_pct.toFixed(0))}٪` : 'هم‌تراز'}
        </span>
      </td>
      <td className='whitespace-nowrap px-3 py-3 text-sm'>{property.agent_name ?? property.agency_name ?? 'بدون تخصیص'}</td>
      <td className='px-3 py-3'><span className={cn('inline-flex whitespace-nowrap rounded-full border px-2 py-0.5 text-xs', freshness.className)}>{freshness.label}</span></td>
      <td className='px-3 py-3'>
        <div className='flex gap-1'>
          <Button aria-label={`جزئیات ${property.title}`} variant='ghost' size='icon-sm' onClick={() => onSelect(property)}><Icons.eye className='size-4' /></Button>
        </div>
      </td>
    </tr>
  );
}

export function PortfolioDesk() {
  const [tab, setTab] = React.useState<DeskTab>('all');
  const [query, setQuery] = React.useState('');
  const [selected, setSelected] = React.useState<PropertySummary | null>(null);
  const inventory = useProperties({ limit: 250 });
  const rows = inventory.data?.items ?? [];
  const filtered = rows.filter((property) => {
    const normalizedQuery = query.trim().toLocaleLowerCase('fa-IR');
    const matchesQuery = !normalizedQuery || [property.title, property.neighborhood, property.city, property.source_ref ?? ''].some((value) => value.toLocaleLowerCase('fa-IR').includes(normalizedQuery));
    if (!matchesQuery) return false;
    if (tab === 'radar') return property.valuation_status === 'BARGAIN';
    if (tab === 'exclusive') return property.source === 'INTERNAL_AGENCY';
    if (tab === 'mine') return Boolean(property.agent_name);
    if (tab === 'stale') return staleMeta(property).className.includes('rose');
    return true;
  });
  const stats = {
    all: rows.length,
    exclusive: rows.filter((property) => property.source === 'INTERNAL_AGENCY').length,
    bargain: rows.filter((property) => property.valuation_status === 'BARGAIN').length,
    stale: rows.filter((property) => staleMeta(property).className.includes('rose')).length
  };

  return (
    <section dir='rtl' className='space-y-5'>
      <div className='flex flex-col justify-between gap-4 rounded-2xl border border-[#ffd8be]/15 bg-[#0c1424]/80 p-5 shadow-2xl shadow-black/20 backdrop-blur-md lg:flex-row lg:items-center'>
        <div>
          <p className='text-xs tracking-[0.2em] text-[#e5a87b]'>PORTFOLIO DESK</p>
          <h2 className='mt-1 text-2xl font-bold text-[#ffd8be]'>کارتابل فایل‌های ملکی دفتر</h2>
          <p className='mt-1 text-sm text-slate-400'>موجودی واقعی نود، رادار شکار و وضعیت پیگیری فایل‌ها</p>
        </div>
        <div className='flex gap-2'>
          <Button className='bg-[#e5a87b] text-[#060b13] hover:bg-[#ffd8be]' render={<Link href='/dashboard/properties/submit' />}><Icons.plusCircle className='size-4' />ثبت مستقیم فایل</Button>
        </div>
      </div>

      <div className='grid gap-3 sm:grid-cols-2 xl:grid-cols-4'>
        {[
          ['کل فایل‌ها', stats.all, 'text-[#ffd8be]'],
          ['انحصاری دفتر', stats.exclusive, 'text-violet-300'],
          ['فرصت شکار', stats.bargain, 'text-emerald-400'],
          ['راکد و پیگیری', stats.stale, 'text-rose-400']
        ].map(([label, value, color]) => (
          <Card key={String(label)} className='border-[#ffd8be]/10 bg-[#0c1424]/70 backdrop-blur-md'>
            <CardContent className='p-4'><p className='text-xs text-slate-400'>{label}</p><p className={cn('mt-2 text-2xl font-bold tabular-nums', color)}>{toPersianDigits(String(value))}</p></CardContent>
          </Card>
        ))}
      </div>

      <Card className='overflow-hidden border-[#ffd8be]/15 bg-[#0c1424]/75 backdrop-blur-md'>
        <CardContent className='space-y-4 p-4'>
          <div className='flex flex-col gap-3 lg:flex-row lg:items-center'>
            <div className='relative flex-1'><Icons.search className='absolute right-3 top-3 size-4 text-muted-foreground' /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder='جستجو بر اساس شناسه، محله یا عنوان فایل...' className='border-[#ffd8be]/15 bg-[#060b13]/70 pr-9' /></div>
            <div className='flex flex-wrap gap-2'>
              {([['all', 'همه'], ['mine', 'فایل‌های من'], ['exclusive', 'انحصاری'], ['radar', 'رادار شکار'], ['stale', 'نیازمند پیگیری']] as const).map(([id, label]) => (
                <Button key={id} size='sm' variant={tab === id ? 'default' : 'outline'} onClick={() => setTab(id)} className={cn(tab === id && 'bg-[#e5a87b] text-[#060b13] hover:bg-[#ffd8be]', tab !== id && 'border-[#ffd8be]/15 bg-transparent')}>{label}</Button>
              ))}
            </div>
          </div>

          {inventory.isPending ? <Skeleton className='h-96 w-full' /> : null}
          {inventory.isError ? <p className='rounded-xl border border-rose-500/25 bg-rose-500/10 p-4 text-sm text-rose-300'>موجودی فایل‌ها دریافت نشد. اتصال نود یا سطح دسترسی را بررسی کنید.</p> : null}
          {!inventory.isPending && !inventory.isError && (
            <div className='max-h-[640px] overflow-auto rounded-xl border border-[#ffd8be]/10'>
              <table className='min-w-[1120px] w-full text-right'>
                <thead className='sticky top-0 z-10 bg-[#060b13]/95 text-xs text-[#ffd8be] backdrop-blur-md'>
                  <tr>{['', 'کد ملک', 'تصویر / عنوان', 'منطقه / موقعیت', 'متراژ / خواب', 'قیمت کل', 'حاشیه شکار', 'مشاور', 'سلامت', 'عملیات'].map((heading) => <th key={heading} className='whitespace-nowrap px-3 py-3 font-medium'>{heading}</th>)}</tr>
                </thead>
                <tbody>{filtered.map((property) => <PortfolioRow key={property.id} property={property} onSelect={setSelected} />)}</tbody>
              </table>
              {filtered.length === 0 && <p className='p-10 text-center text-sm text-muted-foreground'>فایلی با این شرایط پیدا نشد.</p>}
            </div>
          )}
        </CardContent>
      </Card>

      <Sheet open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent side='right' className='w-full border-[#ffd8be]/15 bg-[#060b13] sm:max-w-xl' dir='rtl'>
          {selected && <><SheetHeader><SheetTitle className='text-[#ffd8be]'>{selected.title}</SheetTitle><SheetDescription>{selected.city}، {selected.neighborhood} · {SOURCE_SHORT_LABELS[selected.source]}</SheetDescription></SheetHeader>
          <div className='mt-6 grid grid-cols-2 gap-3 text-sm'>
            <div className='rounded-xl border border-[#ffd8be]/10 bg-[#0c1424] p-3'><p className='text-xs text-muted-foreground'>قیمت کل</p><p className='mt-1 font-semibold'>{formatNumber(selected.total_price)}</p></div>
            <div className='rounded-xl border border-[#ffd8be]/10 bg-[#0c1424] p-3'><p className='text-xs text-muted-foreground'>متراژ</p><p className='mt-1 font-semibold'>{selected.area ? `${toPersianDigits(String(selected.area))} متر` : '---'}</p></div>
            <div className='rounded-xl border border-[#ffd8be]/10 bg-[#0c1424] p-3'><p className='text-xs text-muted-foreground'>مشاور مسئول</p><p className='mt-1 font-semibold'>{selected.agent_name ?? 'بدون تخصیص'}</p></div>
            <div className='rounded-xl border border-[#ffd8be]/10 bg-[#0c1424] p-3'><p className='text-xs text-muted-foreground'>وضعیت ارزش‌گذاری</p><p className='mt-1 font-semibold'>{selected.valuation_status}</p></div>
          </div>
          <p className='mt-5 rounded-xl border border-[#ffd8be]/10 bg-[#0c1424]/70 p-4 text-sm leading-7 text-slate-300'>{selected.description || 'توضیحی برای این فایل ثبت نشده است.'}</p>
          <p className='mt-4 text-xs text-muted-foreground'>اطلاعات تماس مالک و آدرس محرمانه در این نما نمایش داده نمی‌شود و فقط از مسیر مجاز و ثبت‌شده قابل درخواست است.</p>
          <div className='mt-6 flex gap-2'><Button className='bg-[#e5a87b] text-[#060b13] hover:bg-[#ffd8be]' render={<Link href={`/dashboard/properties/${selected.id}`} />}><Icons.eye className='size-4' />جزئیات کامل</Button></div></>}
        </SheetContent>
      </Sheet>
    </section>
  );
}
