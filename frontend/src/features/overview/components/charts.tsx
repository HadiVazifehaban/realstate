'use client';

import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription
} from '@/components/ui/card';
import type { PropertyByCity, PropertyByType, PropertyByStatus } from '../api/types';

interface ChartsProps {
  byCity: PropertyByCity[];
  byType: PropertyByType[];
  byStatus: PropertyByStatus[];
}

export function Charts({ byCity, byType, byStatus }: ChartsProps) {
  return (
    <div className='grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3'>
      <Card>
        <CardHeader>
          <CardTitle>آگهی‌ها بر اساس شهر</CardTitle>
          <CardDescription>توزیع آگهی‌ها در شهرهای مختلف</CardDescription>
        </CardHeader>
        <div className='p-6 space-y-3'>
          {byCity.slice(0, 5).map((item) => (
            <div key={item.city} className='flex items-center justify-between'>
              <span className='text-sm'>{item.city}</span>
              <div className='flex items-center gap-2'>
                <div className='h-2 bg-[#e5a87b] rounded-full' style={{ width: `${(item.count / byCity[0].count) * 100}%` }} />
                <span className='text-sm font-medium'>{item.count.toLocaleString('fa-IR')}</span>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>آگهی‌ها بر اساس نوع</CardTitle>
          <CardDescription>توزیع آگهی‌ها بر اساس نوع ملک</CardDescription>
        </CardHeader>
        <div className='p-6 space-y-3'>
          {byType.map((item) => (
            <div key={item.type} className='flex items-center justify-between'>
              <span className='text-sm'>{item.type}</span>
              <div className='flex items-center gap-2'>
                <div className='h-2 bg-[#ffd8be] rounded-full' style={{ width: `${(item.count / byType[0].count) * 100}%` }} />
                <span className='text-sm font-medium'>{item.count.toLocaleString('fa-IR')}</span>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>آگهی‌ها بر اساس وضعیت</CardTitle>
          <CardDescription>توزیع آگهی‌ها بر اساس وضعیت</CardDescription>
        </CardHeader>
        <div className='p-6 space-y-3'>
          {byStatus.map((item) => (
            <div key={item.status} className='flex items-center justify-between'>
              <span className='text-sm'>{item.status}</span>
              <div className='flex items-center gap-2'>
                <div className='h-2 bg-[#ffd8be] rounded-full' style={{ width: `${(item.count / byStatus[0].count) * 100}%` }} />
                <span className='text-sm font-medium'>{item.count.toLocaleString('fa-IR')}</span>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
