"use client";

import { useQuery } from '@tanstack/react-query';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import PageContainer from '@/components/layout/page-container';
import { fetchScraperStats } from '@/features/ops/api/client';
import { formatCount, formatRate, type ScraperStats } from '@/features/ops/types';

const WINDOW_HOURS = 24;

/**
 * The five phases are the pipeline's design, not an API shape: the node exposes
 * aggregate counters only. Showing a phase that has no counter behind it would
 * be a fabricated metric, so each phase is labelled with the counter that
 * actually feeds it.
 */
function PhaseCard({
  step,
  title,
  metric,
  hint
}: {
  step: number;
  title: string;
  metric: string;
  hint: string;
}) {
  return (
    <Card>
      <CardHeader className='pb-2'>
        <div className='flex items-center gap-2'>
          <Badge variant='secondary'>{step}</Badge>
          <CardTitle className='text-base'>{title}</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className='font-mono text-2xl font-bold'>{metric}</div>
        <p className='text-muted-foreground mt-1 text-xs'>{hint}</p>
      </CardContent>
    </Card>
  );
}

function StatTiles({ stats }: { stats: ScraperStats }) {
  const tiles = [
    { label: "کل جاوب‌ها", value: formatCount(stats.jobs.total) },
    { label: "تکمیل‌شده", value: formatCount(stats.jobs.completed) },
    { label: "در حال اجرا", value: formatCount(stats.jobs.running) },
    { label: "در صف", value: formatCount(stats.jobs.pending) },
    { label: "ناموفق", value: formatCount(stats.jobs.failed) },
    { label: "لغو‌شده", value: formatCount(stats.jobs.cancelled) }
  ];

  return (
    <div className='grid gap-3 sm:grid-cols-3 lg:grid-cols-6'>
      {tiles.map((tile) => (
        <Card key={tile.label}>
          <CardContent className='px-4 py-3'>
            <div className='text-muted-foreground text-xs'>{tile.label}</div>
            <div className='mt-1 font-mono text-xl font-bold'>{tile.value}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function PipelinePage() {
  const { data, isPending, error } = useQuery({
    queryKey: ["ops", "scraper-stats", WINDOW_HOURS],
    queryFn: () => fetchScraperStats(WINDOW_HOURS),
    refetchInterval: 30_000
  });

  return (
    <PageContainer
      pageTitle='پایپ‌لاین پنج فاز'
      pageDescription='وضعیت جاوبی، نرمال‌سازی و دیداپ در بازهٔ ۲۴ ساعت گذشته.'
    >
      {error && (
        <Alert variant='destructive'>
          <AlertTitle>دریافت آمار پایپ‌لاین ناموفق بود</AlertTitle>
          <AlertDescription>{(error as Error).message}</AlertDescription>
        </Alert>
      )}

      {isPending && (
        <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-5'>
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className='h-32' />
          ))}
        </div>
      )}

      {data && (
        <div className='space-y-4'>
          <StatTiles stats={data} />

          <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-5'>
            <PhaseCard
              step={1}
              title='L1 — جاوبی'
              metric={formatCount(data.items.found)}
              hint='رکورد دریافت‌شده از منابع'
            />
            <PhaseCard
              step={2}
              title='L2 — نرمال‌سازی'
              metric={formatCount(data.items.found)}
              hint='همان رکوردها، پس از یکسان‌سازی نواحی'
            />
            <PhaseCard
              step={3}
              title='L3 — AVM'
              metric={formatRate(data.rates.new)}
              hint='نرخ رکوردهای قیمت‌گذاری‌شده'
            />
            <PhaseCard
              step={4}
              title='L4 — دیداپ'
              metric={formatRate(data.rates.duplicate)}
              hint='نرخ تطبیق با رکورد موجود'
            />
            <PhaseCard
              step={5}
              title='L5 — توزیع'
              metric={formatCount(data.items.new)}
              hint='رکورد یکتای منتشرشده'
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle className='text-base'>نرخ‌های کلیدی</CardTitle>
              <CardDescription>
                نسبت به {formatCount(data.items.found)} رکورد در {data.window_hours} ساعت گذشته.
              </CardDescription>
            </CardHeader>
            <CardContent className='space-y-3'>
              <div className='flex items-center gap-3'>
                <span className='w-24 text-sm'>یکتا</span>
                <div className='bg-muted h-2 flex-1 overflow-hidden rounded-full'>
                  <div
                    className='h-full rounded-full bg-emerald-500'
                    style={{ width: formatRate(data.rates.new) }}
                  />
                </div>
                <span className='w-16 text-end font-mono text-xs'>
                  {formatRate(data.rates.new)}
                </span>
              </div>
              <div className='flex items-center gap-3'>
                <span className='w-24 text-sm'>تکراری</span>
                <div className='bg-muted h-2 flex-1 overflow-hidden rounded-full'>
                  <div
                    className='h-full rounded-full bg-amber-500'
                    style={{ width: formatRate(data.rates.duplicate) }}
                  />
                </div>
                <span className='w-16 text-end font-mono text-xs'>
                  {formatRate(data.rates.duplicate)}
                </span>
              </div>
              <div className='flex items-center gap-3'>
                <span className='w-24 text-sm'>ناموفق</span>
                <div className='bg-muted h-2 flex-1 overflow-hidden rounded-full'>
                  <div
                    className='h-full rounded-full bg-red-500'
                    style={{ width: formatRate(data.rates.failure) }}
                  />
                </div>
                <span className='w-16 text-end font-mono text-xs'>
                  {formatRate(data.rates.failure)}
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </PageContainer>
  );
}
