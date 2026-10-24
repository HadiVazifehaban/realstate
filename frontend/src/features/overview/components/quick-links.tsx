'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Icons } from '@/components/icons';
import { cn } from '@/lib/utils';

export function QuickLinks() {
  const links = [
    {
      title: 'افزودن ملک جدید',
      description: 'ثبت آگهی ملک جدید',
      icon: Icons.circleCheck,
      href: '/dashboard/properties/submit',
      color: 'text-green-600'
    },
    {
      title: 'لیست آگهی‌ها',
      description: 'مشاهده همه آگهی‌ها',
      icon: Icons.building,
      href: '/dashboard/properties',
      color: 'text-blue-600'
    },
    {
      title: 'رادار شکار قیمت',
      description: 'فرصت‌های زیر بازار',
      icon: Icons.crosshair,
      href: '/dashboard/properties',
      color: 'text-[#e5a87b]'
    },
    {
      title: 'مدیریت شهر',
      description: 'تغییر شهر فعالیت',
      icon: Icons.mapPin,
      href: '/dashboard/properties',
      color: 'text-purple-600'
    }
  ];

  return (
    <div className='grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4'>
      {links.map((link) => {
        const Icon = link.icon;
        return (
          <Link key={link.title} href={link.href}>
            <Button
              variant='outline'
              className={cn(
                'w-full h-auto flex-col items-start gap-2 p-4 border-[#ffd8be]/20 bg-white/[0.03] hover:border-[#e5a87b]/50 hover:bg-[#e5a87b]/10'
              )}
            >
              <div className={cn('size-8', link.color)}>
                <Icon className='size-full' />
              </div>
              <div className='text-right'>
                <p className='text-sm font-semibold text-white'>{link.title}</p>
                <p className='text-xs text-gray-400'>{link.description}</p>
              </div>
            </Button>
          </Link>
        );
      })}
    </div>
  );
}
