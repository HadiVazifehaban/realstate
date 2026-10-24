'use client';

import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription
} from '@/components/ui/card';
import { Icons } from '@/components/icons';
import { cn } from '@/lib/utils';
import type { NewsItem } from '../api/types';

interface NewsProps {
  news: NewsItem[];
}

export function News({ news }: NewsProps) {
  const formatTime = (timestamp: string) => {
    const now = new Date();
    const time = new Date(timestamp);
    const diff = Math.floor((now.getTime() - time.getTime()) / 1000 / 60 / 60 / 24);

    if (diff < 1) return 'امروز';
    if (diff < 7) return `${diff} روز پیش`;
    return `${Math.floor(diff / 7)} هفته پیش`;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className='flex items-center gap-2'>
          <Icons.circle className='size-5 text-[#e5a87b]' />
          اخبار و اطلاعیه‌ها
        </CardTitle>
        <CardDescription>آخرین اخبار سیستم</CardDescription>
      </CardHeader>
      <div className='p-6 space-y-4'>
        {news.map((item) => (
          <div key={item.id} className={cn(
            'p-3 rounded-lg border transition-all',
            item.is_important
              ? 'border-[#e5a87b]/50 bg-[#e5a87b]/10'
              : 'border-[#ffd8be]/20 bg-white/[0.03]'
          )}>
            <div className='flex items-start justify-between gap-2'>
              <div className='flex-1'>
                <div className='flex items-center gap-2'>
                  <p className='text-sm font-semibold'>{item.title}</p>
                  {item.is_important && (
                    <Icons.circleCheck className='size-3 text-[#e5a87b]' />
                  )}
                </div>
                <p className='text-xs text-muted-foreground mt-1'>{item.content}</p>
              </div>
              <span className='text-xs text-muted-foreground whitespace-nowrap'>
                {formatTime(item.published_at)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
