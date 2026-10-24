'use client';

import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription
} from '@/components/ui/card';
import { Icons } from '@/components/icons';
import { cn } from '@/lib/utils';
import type { AgencyStats, UserStats } from '../api/types';

interface TopListsProps {
  agencyStats: AgencyStats;
  userStats: UserStats;
}

export function TopLists({ agencyStats, userStats }: TopListsProps) {
  return (
    <div className='grid grid-cols-1 gap-4 md:grid-cols-2'>
      <Card>
        <CardHeader>
          <CardTitle className='flex items-center gap-2'>
            <Icons.building className='size-5 text-[#e5a87b]' />
            آژانس‌های برتر
          </CardTitle>
          <CardDescription>آژانس‌ها با بیشترین آگهی</CardDescription>
        </CardHeader>
        <div className='p-6 space-y-3'>
          {agencyStats.top_agencies.map((agency, index) => (
            <div key={index} className='flex items-center justify-between'>
              <div className='flex items-center gap-3'>
                <div className={cn(
                  'w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold',
                  index === 0 ? 'bg-[#e5a87b] text-white' : 'bg-gray-700 text-gray-300'
                )}>
                  {index + 1}
                </div>
                <div>
                  <p className='text-sm font-medium'>{agency.name}</p>
                  <p className='text-xs text-muted-foreground'>{agency.city}</p>
                </div>
              </div>
              <span className='text-sm font-semibold text-[#e5a87b]'>
                {agency.listings_count.toLocaleString('fa-IR')}
              </span>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className='flex items-center gap-2'>
            <Icons.user2 className='size-5 text-[#e5a87b]' />
            مشاوران برتر
          </CardTitle>
          <CardDescription>مشاوران با بیشترین آگهی</CardDescription>
        </CardHeader>
        <div className='p-6 space-y-3'>
          {userStats.top_brokers.map((broker, index) => (
            <div key={index} className='flex items-center justify-between'>
              <div className='flex items-center gap-3'>
                <div className={cn(
                  'w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold',
                  index === 0 ? 'bg-[#e5a87b] text-white' : 'bg-gray-700 text-gray-300'
                )}>
                  {index + 1}
                </div>
                <div>
                  <p className='text-sm font-medium'>{broker.name}</p>
                  <p className='text-xs text-muted-foreground'>{broker.city}</p>
                </div>
              </div>
              <span className='text-sm font-semibold text-[#e5a87b]'>
                {broker.listings_count.toLocaleString('fa-IR')}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
