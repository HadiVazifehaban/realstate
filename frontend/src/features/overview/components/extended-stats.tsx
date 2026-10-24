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
import type { AgencyStats, UserStats, RequestStats, FinancialStats } from '../api/types';

interface ExtendedStatsProps {
  agencyStats: AgencyStats;
  userStats: UserStats;
  requestStats: RequestStats;
  financialStats: FinancialStats;
}

export function ExtendedStats({ agencyStats, userStats, requestStats, financialStats }: ExtendedStatsProps) {
  const formatPrice = (price: number) => {
    return (price / 1000000).toFixed(0) + ' میلیون تومان';
  };

  const cards = [
    {
      title: 'آژانس‌های معاملاتی',
      value: agencyStats.total_agencies.toLocaleString('fa-IR'),
      subValue: `${agencyStats.active_agencies.toLocaleString('fa-IR')} فعال`,
      trend: agencyStats.new_this_month,
      icon: Icons.building,
      description: 'کل آژانس‌های سیستم'
    },
    {
      title: 'کاربران و مشاوران',
      value: userStats.total_users.toLocaleString('fa-IR'),
      subValue: `${userStats.active_brokers.toLocaleString('fa-IR')} مشاور فعال`,
      trend: userStats.new_this_month,
      icon: Icons.user2,
      description: 'کل کاربران سیستم'
    },
    {
      title: 'درخواست‌ها',
      value: requestStats.total_requests.toLocaleString('fa-IR'),
      subValue: `${requestStats.pending.toLocaleString('fa-IR')} در انتظار`,
      trend: requestStats.new_today,
      icon: Icons.archive,
      description: 'کل درخواست‌ها'
    },
    {
      title: 'درآمد این ماه',
      value: formatPrice(financialStats.revenue_this_month),
      subValue: formatPrice(financialStats.revenue_this_year) + ' (سال)',
      trend: financialStats.trend_month,
      icon: Icons.creditCard,
      description: 'درآمد ماهانه'
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
            {card.subValue && (
              <p className='text-xs text-muted-foreground mt-1'>{card.subValue}</p>
            )}
            <CardAction>
              <Badge variant='outline' className={cn(
                card.trend > 0 ? 'text-green-600 border-green-600' : 'text-red-600 border-red-600'
              )}>
                {card.trend > 0 ? <Icons.trendingUp className='size-3' /> : <Icons.trendingDown className='size-3' />}
                {card.trend > 0 ? '+' : ''}{card.trend}
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
