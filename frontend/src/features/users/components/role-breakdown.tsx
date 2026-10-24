"use client";

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Icons } from '@/components/icons';
import { toPersianDigits } from '@/lib/utils';
import type { RoleBreakdown as RoleCount } from '../api/types';
import { ROLES } from '../constants/roles';

/**
 * Role histogram for the current result set.
 *
 * Purely presentational: it renders the `role_breakdown` the users query
 * already returns, so the counts always agree with the rows in the table and no
 * second request is made.
 */
export function RoleBreakdown({ breakdown, total }: { breakdown: RoleCount[]; total: number }) {
  const counts = new Map(breakdown.map((r) => [r.role, r.count]));
  const max = Math.max(1, ...breakdown.map((r) => r.count));

  return (
    <Card>
      <CardHeader>
        <CardTitle>توزیع نقش‌ها</CardTitle>
        <CardDescription>
          {total.toLocaleString('fa-IR')} کاربر در {toPersianDigits(String(ROLES.length))} سطح
          دسترسی
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className='flex flex-col gap-2'>
          {ROLES.map((role) => {
            const count = counts.get(role.value) ?? 0;
            const percent = total > 0 ? Math.round((count / total) * 100) : 0;

            return (
              <li key={role.value} className='flex items-center gap-3'>
                <Badge variant={role.badgeVariant} className='w-24 shrink-0 justify-center'>
                  {role.label}
                </Badge>
                <div
                  className='bg-muted h-2 flex-1 overflow-hidden rounded-full'
                  role='img'
                  aria-label={`${role.label}: ${count} کاربر`}
                >
                  <div
                    className='bg-primary h-full rounded-full transition-[width] duration-300'
                    style={{ width: `${(count / max) * 100}%` }}
                  />
                </div>
                <span className='text-muted-foreground w-16 shrink-0 text-end text-sm tabular-nums'>
                  {count.toLocaleString("fa-IR")}
                </span>
                <span className='text-muted-foreground w-10 shrink-0 text-end text-sm tabular-nums'>
                  {percent.toLocaleString("fa-IR")}٪
                </span>
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}

export function RoleBreakdownSkeleton() {
  return (
    <Card>
      <CardHeader>
        <div className='bg-muted h-5 w-32 animate-pulse rounded' />
        <div className='bg-muted h-4 w-48 animate-pulse rounded' />
      </CardHeader>
      <CardContent className='flex flex-col gap-3'>
        {Array.from({ length: 7 }).map((_, i) => (
          <div key={i} className='flex items-center gap-3'>
            <div className='bg-muted h-5 w-24 animate-pulse rounded' />
            <div className='bg-muted h-2 flex-1 animate-pulse rounded-full' />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

/** Small legend of the permission gates, so the ladder is self-explanatory. */
export function RolePermissionLegend() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>سطح دسترسی نقش‌ها</CardTitle>
        <CardDescription>هر نقش چه عملیاتی را مجاز می‌داند</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className='flex flex-col gap-3'>
          {ROLES.map((role) => (
            <li key={role.value} className='flex flex-col gap-1'>
              <div className='flex items-center gap-2'>
                <Badge variant={role.badgeVariant}>{role.label}</Badge>
                <span className='text-muted-foreground text-xs'>{role.description}</span>
              </div>
              <div className='flex flex-wrap gap-1'>
                {role.canReadPii && <PermissionChip label='مشاهده اطلاعات مالک' />}
                {role.canCloseLead && <PermissionChip label='بستن سرنخ' />}
                {role.isDataGovernor && <PermissionChip label='مدیریت داده و ارزش‌گذاری' />}
                {!role.canReadPii && !role.canCloseLead && !role.isDataGovernor && (
                  <span className='text-muted-foreground text-xs'>دسترسی محدود</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function PermissionChip({ label }: { label: string }) {
  return (
    <span className='text-secondary-foreground bg-secondary inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px]'>
      <Icons.check className='size-3' />
      {label}
    </span>
  );
}
