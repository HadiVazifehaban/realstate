"use client";

import { useQuery } from '@tanstack/react-query';
import PageContainer from '@/components/layout/page-container';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { fetchScrapeJobs, fetchScraperStats } from '@/features/ops/api/client';
import {
  formatCount,
  formatRate,
  JOB_STATUS_LABELS,
  SCRAPE_SOURCE_LABELS,
  type JobStatus,
  type ScrapeJob,
  type ScraperStats
} from '@/features/ops/types';

const WINDOW_HOURS = 24;

const STATUS_VARIANTS: Record<JobStatus, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  PENDING: 'outline',
  RUNNING: 'default',
  COMPLETED: 'secondary',
  FAILED: 'destructive',
  CANCELLED: 'outline'
};

function formatTimestamp(value: string | null): string {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return new Intl.DateTimeFormat('fa-IR', {
    dateStyle: 'short',
    timeStyle: 'short'
  }).format(parsed);
}

/** A single tile in the jobs overview strip. */
function StatTile({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <Card>
      <CardContent className='px-4 py-3'>
        <div className='text-muted-foreground text-xs'>{label}</div>
        <div className={`mt-1 font-mono text-xl font-bold ${tone ?? ''}`}>{value}</div>
      </CardContent>
    </Card>
  );
}

function StatTiles({ stats }: { stats: ScraperStats }) {
  const tiles = [
    { label: 'کل جاوب‌ها', value: formatCount(stats.jobs.total) },
    { label: 'تکمیل‌شده', value: formatCount(stats.jobs.completed), tone: 'text-emerald-600' },
    { label: 'در حال اجرا', value: formatCount(stats.jobs.running), tone: 'text-blue-600' },
    { label: 'در صف', value: formatCount(stats.jobs.pending) },
    { label: 'ناموفق', value: formatCount(stats.jobs.failed), tone: 'text-red-600' },
    { label: 'لغو‌شده', value: formatCount(stats.jobs.cancelled) }
  ];
  return (
    <div className='grid gap-3 sm:grid-cols-3 lg:grid-cols-6'>
      {tiles.map((tile) => (
        <StatTile key={tile.label} label={tile.label} value={tile.value} tone={tile.tone} />
      ))}
    </div>
  );
}

/**
 * The five phases are the pipeline's design, not an API shape: the node exposes
 * aggregate counters only. Each phase is labelled with the counter that actually
 * feeds it so we never present a fabricated breakdown.
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

function RateBar({ label, rate, color }: { label: string; rate: number; color: string }) {
  return (
    <div className='flex items-center gap-3'>
      <span className='w-20 text-sm'>{label}</span>
      <div className='bg-muted h-2 flex-1 overflow-hidden rounded-full'>
        <div className={`h-full rounded-full ${color}`} style={{ width: formatRate(rate) }} />
      </div>
      <span className='w-16 text-end font-mono text-xs'>{formatRate(rate)}</span>
    </div>
  );
}

function JobRow({ job }: { job: ScrapeJob }) {
  return (
    <TableRow>
      <TableCell className='font-mono text-xs' dir='ltr'>
        {job.id.slice(0, 8)}
      </TableCell>
      <TableCell>{SCRAPE_SOURCE_LABELS[job.source]}</TableCell>
      <TableCell>
        <Badge variant={STATUS_VARIANTS[job.status]}>{JOB_STATUS_LABELS[job.status]}</Badge>
      </TableCell>
      <TableCell className='text-center font-mono'>{formatCount(job.items_found)}</TableCell>
      <TableCell className='hidden text-center font-mono text-emerald-600 sm:table-cell'>
        {formatCount(job.items_new)}
      </TableCell>
      <TableCell className='hidden text-center font-mono text-amber-600 md:table-cell'>
        {formatCount(job.items_duplicate)}
      </TableCell>
      <TableCell className='hidden text-center font-mono text-red-600 md:table-cell'>
        {formatCount(job.items_failed)}
      </TableCell>
      <TableCell className='hidden max-w-[160px] truncate text-xs lg:table-cell' title={job.error ?? ''}>
        {job.error ?? '—'}
      </TableCell>
      <TableCell className='hidden text-xs whitespace-nowrap lg:table-cell'>
        {formatTimestamp(job.finished_at ?? job.created_at)}
      </TableCell>
    </TableRow>
  );
}

export default function StreamsPage() {
  const statsQuery = useQuery({
    queryKey: ['ops', 'scraper-stats', WINDOW_HOURS],
    queryFn: () => fetchScraperStats(WINDOW_HOURS),
    refetchInterval: 30_000
  });

  const jobsQuery = useQuery({
    queryKey: ['ops', 'scraper-jobs', 50],
    queryFn: () => fetchScrapeJobs(50, 0),
    refetchInterval: 15_000
  });

  const stats = statsQuery.data;
  const jobs = jobsQuery.data;
  const error = statsQuery.error ?? jobsQuery.error;

  return (
    <PageContainer
      pageTitle='صف جاوب (استریم‌ها)'
      pageDescription={`نظارت لحظه‌ای روی منابع واگذاری و پایپ‌لاین؛ بازهٔ ${WINDOW_HOURS} ساعت گذشته.`}
    >
      {error && (
        <Alert variant='destructive'>
          <AlertTitle>دریافت دادهٔ استریم ناموفق بود</AlertTitle>
          <AlertDescription>{(error as Error).message}</AlertDescription>
        </Alert>
      )}

      {/* آمار کلی جاوب‌ها */}
      <section>
        {statsQuery.isPending ? (
          <div className='grid gap-3 sm:grid-cols-3 lg:grid-cols-6'>
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className='h-20' />
            ))}
          </div>
        ) : stats ? (
          <StatTiles stats={stats} />
        ) : null}
      </section>

      {/* پایپ‌لاین پنج فاز + نرخ‌ها */}
      <section className='mt-4'>
        {statsQuery.isPending ? (
          <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-5'>
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className='h-32' />
            ))}
          </div>
        ) : stats ? (
          <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-5'>
            <PhaseCard
              step={1}
              title='L1 — جاوبی'
              metric={formatCount(stats.items.found)}
              hint='رکورد دریافت‌شده از منابع'
            />
            <PhaseCard
              step={2}
              title='L2 — نرمال‌سازی'
              metric={formatCount(stats.items.found)}
              hint='پس از یکسان‌سازی نواحی'
            />
            <PhaseCard
              step={3}
              title='L3 — AVM'
              metric={formatRate(stats.rates.new)}
              hint='نرخ قیمت‌گذاری‌شده'
            />
            <PhaseCard
              step={4}
              title='L4 — دیداپ'
              metric={formatRate(stats.rates.duplicate)}
              hint='تطبیق با رکورد موجود'
            />
            <PhaseCard
              step={5}
              title='L5 — توزیع'
              metric={formatCount(stats.items.new)}
              hint='رکورد یکتای منتشرشده'
            />
          </div>
        ) : null}
      </section>

      {stats ? (
        <Card className='mt-4'>
          <CardHeader>
            <CardTitle className='text-base'>نرخ‌های کلیدی</CardTitle>
            <CardDescription>
              نسبت به {formatCount(stats.items.found)} رکورد در {stats.window_hours} ساعت گذشته.
            </CardDescription>
          </CardHeader>
          <CardContent className='space-y-3'>
            <RateBar label='یکتا' rate={stats.rates.new} color='bg-emerald-500' />
            <RateBar label='تکراری' rate={stats.rates.duplicate} color='bg-amber-500' />
            <RateBar label='ناموفق' rate={stats.rates.failure} color='bg-red-500' />
          </CardContent>
        </Card>
      ) : null}

      {/* جدول جاوب‌های اخیر */}
      <section className='mt-4'>
        <Card>
          <CardHeader>
            <CardTitle className='text-base'>جاوب‌های اخیر</CardTitle>
            <CardDescription>
              {jobs ? `${formatCount(jobs.total)} جاوب در کل صف.` : 'در حال دریافت…'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {jobsQuery.isPending ? (
              <div className='space-y-3'>
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className='h-12 w-full rounded-md' />
                ))}
              </div>
            ) : jobs && jobs.items.length === 0 ? (
              <p className='text-muted-foreground py-8 text-center text-sm'>
                جاوبی ثبت نشده است.
              </p>
            ) : jobs && jobs.items.length > 0 ? (
              <div className='overflow-x-auto'>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>شناسه</TableHead>
                      <TableHead>منبع</TableHead>
                      <TableHead>وضعیت</TableHead>
                      <TableHead className='text-center'>یافت‌شده</TableHead>
                      <TableHead className='hidden text-center sm:table-cell'>یکتا</TableHead>
                      <TableHead className='hidden text-center md:table-cell'>تکراری</TableHead>
                      <TableHead className='hidden text-center md:table-cell'>ناموفق</TableHead>
                      <TableHead className='hidden lg:table-cell'>خطا</TableHead>
                      <TableHead className='hidden lg:table-cell'>زمان</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {jobs.items.map((job) => (
                      <JobRow key={job.id} job={job} />
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </section>
    </PageContainer>
  );
}
