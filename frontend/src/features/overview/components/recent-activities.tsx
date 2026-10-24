'use client';

import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription
} from '@/components/ui/card';
import { Icons } from '@/components/icons';
import { cn } from '@/lib/utils';
import type { RecentActivity } from '../api/types';

interface RecentActivitiesProps {
  activities: RecentActivity[];
}

export function RecentActivities({ activities }: RecentActivitiesProps) {
  const getIcon = (type: RecentActivity['type']) => {
    switch (type) {
      case 'new_listing':
        return Icons.circleCheck;
      case 'radar_deal':
        return Icons.crosshair;
      case 'user_change':
        return Icons.user2;
      case 'new_agency':
        return Icons.building;
      case 'new_request':
        return Icons.archive;
      default:
        return Icons.circle;
    }
  };

  const getIconColor = (type: RecentActivity['type']) => {
    switch (type) {
      case 'new_listing':
        return 'text-green-600';
      case 'radar_deal':
        return 'text-[#e5a87b]';
      case 'user_change':
        return 'text-blue-600';
      case 'new_agency':
        return 'text-purple-600';
      case 'new_request':
        return 'text-orange-600';
      default:
        return 'text-gray-600';
    }
  };

  const formatTime = (timestamp: string) => {
    const now = new Date();
    const time = new Date(timestamp);
    const diff = Math.floor((now.getTime() - time.getTime()) / 1000 / 60);

    if (diff < 1) return 'همین الان';
    if (diff < 60) return `${diff} دقیقه پیش`;
    if (diff < 1440) return `${Math.floor(diff / 60)} ساعت پیش`;
    return `${Math.floor(diff / 1440)} روز پیش`;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>فعالیت‌های اخیر</CardTitle>
        <CardDescription>آخرین تغییرات در سیستم</CardDescription>
      </CardHeader>
      <div className='p-6 space-y-4'>
        {activities.map((activity) => {
          const Icon = getIcon(activity.type);
          return (
            <div key={activity.id} className='flex items-start gap-3'>
              <div className={cn('mt-0.5', getIconColor(activity.type))}>
                <Icon className='size-4' />
              </div>
              <div className='flex-1 min-w-0'>
                <p className='text-sm font-medium truncate'>{activity.title}</p>
                <p className='text-xs text-muted-foreground truncate'>{activity.description}</p>
                {activity.city && (
                  <p className='text-xs text-[#e5a87b] mt-1'>{activity.city}</p>
                )}
              </div>
              <span className='text-xs text-muted-foreground whitespace-nowrap'>
                {formatTime(activity.timestamp)}
              </span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
