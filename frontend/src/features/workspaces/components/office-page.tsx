"use client";

import * as React from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';

import { Icons } from '@/components/icons';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuthContext } from '@/hooks/use-auth';
import { getRoleMeta, ROLES } from '@/features/users/constants/roles';
import { toPersianDigits } from '@/lib/utils';

import { licenseStatusQueryOptions, officeRosterQueryOptions } from '../api/queries';
import { licenseStatusMeta, nodeModeLabel, StatusTone } from '../types';

function toneToBadgeVariant(tone: StatusTone | undefined): 'default' | 'secondary' | 'outline' | 'ghost' | 'destructive' {
  switch (tone) {
    case 'bad':
      return 'destructive';
    case 'warn':
      return 'secondary';
    default:
      return 'default';
  }
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '---';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '---';
  return new Intl.DateTimeFormat('fa-IR', { dateStyle: 'medium' }).format(parsed);
}

const count = (value: number | null | undefined) =>
  value === null || value === undefined ? '---' : toPersianDigits(value.toLocaleString('en-US'));

function daysUntil(value: string | null | undefined): number | null {
  if (!value) return null;
  const parsed = new Date(value).getTime();
  if (Number.isNaN(parsed)) return null;
  return Math.ceil((parsed - Date.now()) / 86400000);
}

function RoleBreakdown({ roleCounts, maxRoleCount }: { roleCounts: Map<string, number>; maxRoleCount: number }) {
  return (
    <div className='flex flex-wrap gap-3'>
      {ROLES.map((role) => {
        const numberOfUsers = roleCounts.get(role.value) ?? 0;
        const percentage = maxRoleCount > 0 ? Math.round((numberOfUsers / maxRoleCount) * 100) : 0;
        return (
          <div key={role.value} className='flex-1 min-w-[100px]'>
            <div className='flex justify-between text-xs mb-1'>
              <span className='text-muted-foreground'>{role.label}</span>
              <span className='font-medium text-foreground'>{numberOfUsers} ({percentage}%)</span>
            </div>
            <div className='h-2 rounded-full bg-muted overflow-hidden'>
              <div
                className='h-full rounded-full transition-all duration-500'
                style={{ background: 'var(--primary)', width: `${Math.max(percentage, 3)}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PermissionBadge({ label, icon }: { label: string; icon: keyof typeof Icons }) {
  const Icon = Icons[icon];
  return (
    <span className='inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1.5 text-xs font-medium ring-1 ring-primary/20'>
      <Icon aria-hidden className='size-3.5 text-primary' />
      {label}
    </span>
  );
}

function StatusChip({ status, isUsable }: { status: string; isUsable: boolean }) {
  const meta = licenseStatusMeta(status);
  return (
    <>
      <Badge variant={toneToBadgeVariant(meta.tone)} className='px-3 py-1.5 text-sm font-medium'>
        {meta.label}
      </Badge>
      <Badge variant='outline' className='px-2.5 py-1 font-normal'>
        {isUsable ? 'آماده به کار' : 'نیاز به بررسی'}
      </Badge>
    </>
  );
}

export default function OfficePage() {
  const license = useQuery(licenseStatusQueryOptions());
  const roster = useQuery(officeRosterQueryOptions());
  const auth = useAuthContext();
  const meta = license.data ? licenseStatusMeta(license.data.status) : null;
  const graceDays = daysUntil(license.data?.offline_grace_deadline);
  const roleCounts = new Map((roster.data?.role_breakdown ?? []).map((entry) => [entry.role, entry.count]));
  const maxRoleCount = Math.max(1, ...roleCounts.values());

  return (
    <div className='space-y-6' dir='rtl'>
      <div className='relative overflow-hidden rounded-2xl border border-border/60 bg-gradient-to-br from-primary/5 via-background to-accent/10 p-6 shadow-sm md:p-8'>
        <h2 className='text-2xl font-bold text-foreground'>{license.data?.agency_name || 'دفتر من'}</h2>
        <p className='text-muted-foreground mt-1 text-sm'>وضعیت پروانه، دسترسی‌ها و اعضای تیم شما در یک نگاه</p>
      </div>

      <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-4'>
        <div className='rounded-2xl border border-[rgba(255,255,255,0.12)] bg-gradient-to-br from-card to-card/80 p-5 shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg'>
          <div className='flex items-center gap-4'>
            <Icons.home className='size-5 text-primary' />
            <div>
              <div className='text-xs text-muted-foreground'>نام دفتر</div>
              <div className='text-xl font-semibold text-foreground'>{license.data?.agency_name ?? '---'}</div>
            </div>
          </div>
        </div>

        <div className='rounded-2xl border border-[rgba(255,255,255,0.12)] bg-gradient-to-br from-card to-card/80 p-5 shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg'>
          <div className='flex items-center gap-4'>
            <Icons.user className='size-5 text-primary' />
            <div>
              <div className='text-xs text-muted-foreground'>نشست‌های هم‌زمان مجاز</div>
              <div className='text-xl font-semibold text-foreground'>{count(license.data?.max_concurrent_users) ?? '---'}</div>
            </div>
          </div>
        </div>

        <div className='rounded-2xl border border-[rgba(255,255,255,0.12)] bg-gradient-to-br from-card to-card/80 p-5 shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg'>
          <div className='flex items-center gap-4'>
            <Icons.teams className='size-5 text-primary' />
            <div>
              <div className='text-xs text-muted-foreground'>کاربران دفتر</div>
              <div className='text-xl font-semibold text-foreground'>{count(roster.data?.total_users) ?? '---'}</div>
            </div>
          </div>
        </div>

        <div className='rounded-2xl border border-[rgba(255,255,255,0.12)] bg-gradient-to-br from-amber-500/20 to-amber-600/5 p-5 shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg'>
          <div className='flex items-center gap-4'>
            <Icons.badgeCheck className='size-5 text-amber-dark ring-amber-accent/30' />
            <div>
              <div className='text-xs text-muted-foreground'>وضعیت پروانه</div>
              <div className='text-xl font-semibold text-foreground'>{meta?.label ?? '---'}</div>
            </div>
          </div>
        </div>
      </div>

      {license.isError && (
        <Alert variant='destructive'>
          <AlertTitle>دریافت وضعیت پروانه ناموفق بود</AlertTitle>
          <AlertDescription>{(license.error as Error)?.message ?? 'ارتباط با نود برقرار نشد.'}</AlertDescription>
        </Alert>
      )}

      <div className='grid items-start gap-4 lg:grid-cols-2'>
        <Card className='border-border/60'>
          <CardHeader className='rounded-t-2xl'>
            <CardTitle className='flex items-center gap-2.5 text-base font-semibold'>
              <span className='bg-gradient-to-br from-amber-500/25 to-amber-600/10 text-amber-dark ring-1 ring-amber-accent/30 flex size-9 items-center justify-center rounded-xl'>
                <Icons.badgeCheck className='size-5' />
              </span>
              پروانهٔ نود
            </CardTitle>
            <CardDescription>وضعیت پروانهٔ تجاری این دفتر روی همین نود.</CardDescription>
          </CardHeader>
          <CardContent className='space-y-3 px-4'>
            {license.isPending ? <Skeleton className='h-44 w-full' /> : null}
            {license.data && (
              <>
                <div className='flex flex-wrap items-center gap-2'>
                  <Badge variant={toneToBadgeVariant(meta?.tone)} className='px-3 py-1.5 text-sm font-medium'>{meta?.label ?? '---'}</Badge>
                  <Badge variant='outline' className='px-2.5 py-1 font-normal'>{nodeModeLabel(license.data.node_mode)}</Badge>
                </div>
                <dl className='grid grid-cols-1 gap-2.5 sm:grid-cols-2'>
                  <div className='rounded-xl bg-card/50 p-3.5'><dt className='text-xs font-medium uppercase tracking-wider text-muted-foreground'>شناسهٔ پروانه</dt><dd className='mt-1 truncate text-sm font-medium'>{license.data.license_id ?? '---'}</dd></div>
                  <div className='rounded-xl bg-card/50 p-3.5'><dt className='text-xs font-medium uppercase tracking-wider text-muted-foreground'>مهلت آفلاین (روز)</dt><dd className='mt-1 truncate text-sm font-medium'>{count(license.data.grace_days)}</dd></div>
                  <div className='rounded-xl bg-card/50 p-3.5'><dt className='text-xs font-medium uppercase tracking-wider text-muted-foreground'>صدور</dt><dd className='mt-1 truncate text-sm font-medium'>{formatDate(license.data.issued_at)}</dd></div>
                  <div className='rounded-xl bg-card/50 p-3.5'><dt className='text-xs font-medium uppercase tracking-wider text-muted-foreground'>انقضا</dt><dd className='mt-1 truncate text-sm font-medium'>{formatDate(license.data.expires_at)}</dd></div>
                </dl>
                {graceDays !== null && license.data.status === 'GRACE_PERIOD' && (
                  <div className='rounded-xl border border-amber-200/40 bg-amber-50/80 px-4 py-3'>
                    <p className='text-sm'><span className='text-amber-800'>{graceDays >= 0 ? `${count(graceDays)} روز تا پایان مهلت آفلاین؛ برای تمدید، نود را به شبکه وصل کنید.` : 'مهلت آفلاین گذشته است؛ نود را به شبکه وصل کنید.'}</span></p>
                  </div>
                )}
                {license.data.features.length > 0 && (
                  <div className='flex flex-wrap gap-1.5 pt-1'>
                    {license.data.features.map((feature) => <Badge key={feature} variant='secondary' className='font-normal'>{feature}</Badge>)}
                  </div>
                )}
                {license.data.machine_fingerprint_hash && (
                  <div className='rounded-xl bg-card/50 p-3.5'><dt className='text-xs font-medium uppercase tracking-wider text-muted-foreground'>اثر انگیک سخت‌افزاری</dt><dd className='mt-1 truncate font-mono text-xs text-muted-foreground/80'>{license.data.machine_fingerprint_hash}</dd></div>
                )}
                {license.data.reason && <p className='text-xs text-muted-foreground/80'>پیام نود: <span dir='ltr'>{license.data.reason}</span></p>}
              </>
            )}
          </CardContent>
        </Card>

        <Card className='border-border/60 bg-card/40'>
          <CardHeader className='rounded-t-2xl pb-4'>
            <div className='flex items-center justify-between gap-4'>
              <div className='flex items-center gap-2.5'>
                <span className='bg-gradient-to-br from-primary/25 to-primary/10 text-primary ring-1 ring-primary/30 flex size-9 items-center justify-center rounded-xl'>
                  <Icons.user className='size-5' />
                </span>
                <div>
                  <CardTitle className='text-base font-semibold'>دسترسی من</CardTitle>
                  <CardDescription className='text-xs text-muted-foreground'>نقش‌های فعال در توکن ورود</CardDescription>
                </div>
              </div>
              <Button variant='ghost' size='sm' render={<Link href='/dashboard/users' />}>مدیریت کاربران</Button>
            </div>
          </CardHeader>
          <CardContent className='space-y-3 pt-4'>
            {auth.isLoading ? <Skeleton className='h-32 w-full' /> : null}
            {auth.roles.length === 0 ? (
              <div className='rounded-xl border border-border/60 bg-muted/30 p-4 text-xs text-muted-foreground'>نقری روی توکن تنظیم نشده است.</div>
            ) : (
              <>
                <div className='flex flex-wrap gap-2'>
                  {auth.roles.map((role) => {
                    const roleMeta = getRoleMeta(role.replace(/^ROLE_/, ''));
                    return <Badge key={role} variant={roleMeta.badgeVariant} className='px-3 py-1.5 text-xs font-medium'>{roleMeta.label}</Badge>;
                  })}
                </div>
                {auth.roles.some((role) => getRoleMeta(role.replace(/^ROLE_/, '')).canReadPii) && <PermissionBadge label='مشاهدهٔ اطلاعات مالک' icon='eye' />}
                {auth.roles.some((role) => getRoleMeta(role.replace(/^ROLE_/, '')).canCloseLead) && <PermissionBadge label='بستن معامله' icon='check' />}
                {auth.roles.some((role) => getRoleMeta(role.replace(/^ROLE_/, '')).isDataGovernor) && <PermissionBadge label='مدیریت داده و ارزش‌گذاری' icon='exclusive' />}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className='border-border/60 bg-card/40'>
        <CardHeader className='flex-row items-start justify-between gap-4 rounded-t-2xl pb-4'>
          <div className='space-y-1'>
            <CardTitle className='flex items-center gap-2.5 text-base font-semibold'>
              <span className='bg-gradient-to-br from-primary/25 to-primary/10 text-primary ring-1 ring-primary/30 flex size-9 items-center justify-center rounded-xl'>
                <Icons.teams className='size-5' />
              </span>
              تیم دفتر
            </CardTitle>
            <CardDescription className='text-xs text-muted-foreground'>توزیع نقش‌ها میان کاربران این دفتر، از دفترچه کاربران نود.</CardDescription>
          </div>
          <div className='flex shrink-0 gap-2'>
            <Button variant='outline' size='sm' render={<Link href='/dashboard/workspaces/team' />}>فهرست تیم</Button>
            <Button size='sm' render={<Link href='/dashboard/users' />}>مدیریت کاربران</Button>
          </div>
        </CardHeader>
        <CardContent className='px-4'>
          {roster.isError && <p className='text-destructive text-xs'>{(roster.error as Error)?.message ?? 'دریافت فهرست کاربران ناموفق بود.'}</p>}
          {roster.isPending && <Skeleton className='h-32 w-full' />}
          {roster.data && roleCounts.size > 0 && (
            <div className='flex flex-wrap gap-3'>
              {ROLES.map((role) => {
                const numberOfUsers = roleCounts.get(role.value) ?? 0;
                const percentage = maxRoleCount > 0 ? Math.round((numberOfUsers / maxRoleCount) * 100) : 0;
                return (
                  <div key={role.value} className='flex-1 min-w-[100px]'>
                    <div className='flex justify-between text-xs mb-1'>
                      <span className='text-muted-foreground'>{role.label}</span>
                      <span className='font-medium text-foreground'>{numberOfUsers} ({percentage}%)</span>
                    </div>
                    <div className='h-2 rounded-full bg-muted overflow-hidden'>
                      <div className='h-full rounded-full bg-primary/30' style={{ width: `${Math.max(percentage, 3)}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          {roster.data && roleCounts.size === 0 && <div className='py-8 text-center text-sm text-muted-foreground'>هنوز کاربری در این دفتر نیست.</div>}
        </CardContent>
      </Card>
    </div>
  );
}
