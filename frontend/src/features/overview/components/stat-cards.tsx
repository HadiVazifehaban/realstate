'use client';

import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardHeader,
  CardDescription,
  CardTitle,
  CardAction,
  CardFooter
} from '@/components/ui/card';
import { Icons } from '@/components/icons';
import { cn } from '@/lib/utils';
import type { OverviewStats } from '../api/types';

interface StatCardsProps {
  stats: OverviewStats;
}

export function StatCards({ stats }: StatCardsProps) {
  const cards = [
    {
      title: 'کل آگهی‌ها',
      value: stats.total_listings.toLocaleString('fa-IR'),
      trend: stats.trends.total_listings,
      description: 'همه آگهی‌های سیستم'
    },
    {
      title: 'ویترین خرید',
      value: stats.showcase_buy.toLocaleString('fa-IR'),
      trend: stats.trends.showcase_buy,
      description: 'آگهی‌های فروش ویژه'
    },
    {
      title: 'ویترین اجاره',
      value: stats.showcase_rent.toLocaleString('fa-IR'),
      trend: stats.trends.showcase_rent,
      description: 'آگهی‌های اجاره ویژه'
    },
    {
      title: 'رادار شکار قیمت',
      value: stats.radar_deals.toLocaleString('fa-IR'),
      trend: stats.trends.radar_deals,
      description: 'فرصت‌های زیر بازار'
    }
  ];

  return (
    <div className='*:data-[slot=card]:from-primary/5 *:data-[slot=card]:to-card dark:*:data-[slot=card]:bg-card grid grid-cols-1 gap-4 *:data-[slot=card]:bg-gradient-to-t *:data-[slot=card]:shadow-xs md:grid-cols-2 lg:grid-cols-4'>
      {cards.map((card, index) => (
        <Card key={index} className='@container/card'>
          <CardHeader>
            <CardDescription>{card.title}</CardDescription>
            <CardTitle className='text-2xl font-semibold tabular-nums @[250px]/card:text-3xl'>
              {card.value}
            </CardTitle>
            <CardAction>
              <Badge variant='outline' className={cn(
                card.trend > 0 ? 'text-green-600 border-green-600' : 'text-red-600 border-red-600'
              )}>
                {card.trend > 0 ? <Icons.trendingUp className='size-3' /> : <Icons.trendingDown className='size-3' />}
                {card.trend > 0 ? '+' : ''}{card.trend}%
              </Badge>
            </CardAction>
          </CardHeader>
          <CardFooter className='flex-col items-start gap-1.5 text-sm'>
            <div className='line-clamp-1 flex gap-2 font-medium'>
              {card.trend > 0 ? 'روند صعودی' : 'روند نزولی'} این ماه
              {card.trend > 0 ? <Icons.trendingUp className='size-4 text-green-600' /> : <Icons.trendingDown className='size-4 text-red-600' />}
            </div>
            <div className='text-muted-foreground'>{card.description}</div>
          </CardFooter>
        </Card>
      ))}
    </div>
  );
}
