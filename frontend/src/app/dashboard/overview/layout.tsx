'use client';

import PageContainer from '@/components/layout/page-container';
import { StatCards } from '@/features/overview/components/stat-cards';
import { ExtendedStats } from '@/features/overview/components/extended-stats';
import { Charts } from '@/features/overview/components/charts';
import { TopLists } from '@/features/overview/components/top-lists';
import { FeaturedListings } from '@/features/overview/components/featured-listings';
import { RecentActivities } from '@/features/overview/components/recent-activities';
import { News } from '@/features/overview/components/news';
import { QuickLinks } from '@/features/overview/components/quick-links';
import { overviewDataQueryOptions } from '@/features/overview/api/queries';
import { useSuspenseQuery } from '@tanstack/react-query';

export default function OverViewLayout() {
  const { data } = useSuspenseQuery(overviewDataQueryOptions());

  return (
    <PageContainer>
      <div className='flex flex-1 flex-col gap-6'>
        <div className='flex items-center justify-between'>
          <h2 className='text-2xl font-bold tracking-tight'>سلام، خوش آمدید 👋</h2>
        </div>

        <StatCards stats={data.stats} />

        <ExtendedStats
          agencyStats={data.agency_stats}
          userStats={data.user_stats}
          requestStats={data.request_stats}
          financialStats={data.financial_stats}
        />

        <div>
          <h3 className='text-lg font-semibold mb-3'>لینک‌های سریع</h3>
          <QuickLinks />
        </div>

        <TopLists
          agencyStats={data.agency_stats}
          userStats={data.user_stats}
        />

        <Charts
          byCity={data.by_city}
          byType={data.by_type}
          byStatus={data.by_status}
        />

        <div className='grid grid-cols-1 gap-4 md:grid-cols-2'>
          <FeaturedListings listings={data.featured_listings} />
          <News news={data.news} />
        </div>

        <RecentActivities activities={data.recent_activities} />
      </div>
    </PageContainer>
  );
}
