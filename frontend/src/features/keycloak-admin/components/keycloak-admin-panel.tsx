'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import PageContainer from '@/components/layout/page-container';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuthContext } from '@/hooks/use-auth';
import { fetchKeycloakConfig, fetchKeycloakDashboard, fetchKeycloakResource } from '../api';

const labels: Record<string, string> = {
  dashboard: 'داشبورد Keycloak', users: 'کاربران', groups: 'گروه‌ها', roles: 'نقش‌ها',
  clients: 'Clientها', 'client-scopes': 'Client Scopeها', 'realm-settings': 'تنظیمات Realm',
  authentication: 'Authentication Flowها', 'identity-providers': 'Identity Providerها',
  'user-federation': 'User Federation', events: 'رویدادها',
  'admin-permissions': 'مجوزهای مدیر', 'not-found': 'صفحه پیدا نشد'
};
const apiResource: Record<string, string> = {
  users: 'users', groups: 'groups', roles: 'roles', clients: 'clients',
  'client-scopes': 'client-scopes', 'realm-settings': 'realm-settings',
  authentication: 'authentication', 'identity-providers': 'identity-providers',
  'user-federation': 'user-federation', events: 'events',
  'admin-permissions': 'admin-permissions'
};
const sections = Object.entries(labels).filter(([key]) => key !== 'not-found');

function errorStatus(error: unknown): number | undefined {
  return error instanceof Error ? (error as Error & { status?: number }).status : undefined;
}

export function KeycloakAdminPanel({ resource }: { resource: string }) {
  const { roles, isLoading: authLoading } = useAuthContext();
  const allowed = roles.includes('ROLE_ADMIN');
  const [search, setSearch] = useState('');
  const config = useQuery({ queryKey: ['keycloak-admin', 'config'], queryFn: fetchKeycloakConfig, enabled: !authLoading && allowed, retry: false });
  const dashboard = useQuery({ queryKey: ['keycloak-admin', 'dashboard'], queryFn: fetchKeycloakDashboard, enabled: !authLoading && allowed && resource === 'dashboard', retry: false });
  const listing = useQuery({
    queryKey: ['keycloak-admin', resource, search],
    queryFn: () => fetchKeycloakResource(config.data!.realm, apiResource[resource], 0, 25, search),
    enabled: !authLoading && allowed && !!config.data?.realm && !!apiResource[resource], retry: false
  });

  useEffect(() => {
    if (typeof document !== 'undefined') document.documentElement.dir = 'rtl';
  }, []);

  const title = labels[resource] ?? labels['not-found'];
  const forbidden = (error: unknown) => errorStatus(error) === 403;
  const sessionExpired = (error: unknown) => errorStatus(error) === 401;
  const activeError = resource === 'dashboard' ? dashboard.error : listing.error;
  const navigation = useMemo(() => sections, []);

  if (authLoading) return <PageContainer pageTitle="مدیریت Keycloak"><Skeleton className="h-56 w-full" /></PageContainer>;
  if (!allowed) return <PageContainer pageTitle="مدیریت Keycloak" access={false} accessFallback={<p role="alert">دسترسی غیرمجاز — این بخش فقط برای مدیر کل سامانه در دسترس است.</p>}><></></PageContainer>;
  if (resource === 'not-found') return <PageContainer pageTitle={title}><p>این صفحه در پنل تعریف نشده است.</p></PageContainer>;

  return (
    <PageContainer pageTitle={title} pageDescription="مدیریت Realm از طریق نشست فعلی و مجوزهای واقعی Keycloak؛ هیچ اعتبارنامه یا Secret نمایش داده نمی‌شود.">
      <div dir="rtl" className="space-y-5">
        <nav aria-label="بخش‌های مدیریت Keycloak" className="flex flex-wrap gap-2">
          {navigation.map(([key, label]) => <Link key={key} href={key === 'dashboard' ? '/dashboard/settings/keycloak' : `/dashboard/settings/keycloak/${key}`} className={`inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${resource === key ? 'border-primary bg-primary text-primary-foreground' : 'border-input bg-background'}`}>{label}</Link>)}
        </nav>
        <Alert>
          <AlertTitle>مجوز مستقل Keycloak الزامی است</AlertTitle>
          <AlertDescription>نقش ROLE_ADMIN سامانه به‌تنهایی مجوز Admin API نیست. دسترسی فقط با Realm Role تأییدشده و realm-management role در توکن فعلی پذیرفته می‌شود.</AlertDescription>
        </Alert>
        {config.error && <Alert variant="destructive"><AlertTitle>{sessionExpired(config.error) ? 'نشست منقضی شده' : forbidden(config.error) ? 'مجوز Keycloak کافی نیست' : 'خطا در دریافت پیکربندی'}</AlertTitle><AlertDescription>{config.error.message}</AlertDescription></Alert>}
        {activeError && <Alert variant="destructive"><AlertTitle>{sessionExpired(activeError) ? 'نشست منقضی شده' : forbidden(activeError) ? 'مجوز Keycloak کافی نیست' : 'خطا در دریافت داده'}</AlertTitle><AlertDescription>{activeError.message}</AlertDescription></Alert>}

        {resource === 'dashboard' && <>
          {dashboard.isLoading && <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 5 }, (_, index) => <Skeleton key={index} className="h-28" />)}</div>}
          {dashboard.data && <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              <Metric title="Realm فعال" value={dashboard.data.realm} />
              {Object.entries(dashboard.data.metrics).map(([key, value]) => <Metric key={key} title={key} value={value === null ? 'در دسترس نیست' : value} />)}
            </div>
            <Card><CardHeader><CardTitle>مجوزهای مدیر جاری</CardTitle><CardDescription>برگرفته از claimهای امضاشدهٔ Client Role، جدا از ROLE_ADMIN Realm</CardDescription></CardHeader><CardContent className="flex flex-wrap gap-2"><Badge>ROLE_ADMIN</Badge>{dashboard.data.adminPermissions.realmManagementRoles.map((role) => <Badge key={role} variant="outline">{role}</Badge>)}{dashboard.data.adminPermissions.realmManagementRoles.length === 0 && <p className="text-sm text-muted-foreground">هیچ مجوز realm-management در توکن فعلی وجود ندارد.</p>}</CardContent></Card>
          </>}
        </>}

        {apiResource[resource] && <>
          <div className="flex flex-wrap items-center gap-3"><Input aria-label="جستجو" placeholder="جستجو در داده‌های Keycloak…" value={search} onChange={(event) => setSearch(event.target.value)} className="max-w-md" /><Button variant="outline" onClick={() => void listing.refetch()} disabled={listing.isFetching}>بروزرسانی</Button></div>
          {listing.isLoading && <Skeleton className="h-52 w-full" />}
          {listing.data && <Card><CardHeader><CardTitle>{title}</CardTitle><CardDescription>Realm: {config.data?.realm} · صفحهٔ اول، حداکثر {listing.data.limit ?? 25} مورد</CardDescription></CardHeader><CardContent>
            {listing.data.items.length === 0 ? <p className="py-8 text-center text-muted-foreground">داده‌ای برای نمایش وجود ندارد یا API این قابلیت را با مجوز فعلی ارائه نمی‌کند.</p> : <div className="overflow-x-auto"><table className="w-full min-w-[36rem] text-sm"><thead><tr className="border-b text-start">{['شناسه', 'نام کاربری / نام', 'ایمیل / مسیر', 'وضعیت'].map((field) => <th key={field} className="p-3 text-start">{field}</th>)}</tr></thead><tbody>{listing.data.items.map((item, index) => <tr key={String(item.id ?? index)} className="border-b last:border-0"><td className="max-w-48 truncate p-3 font-mono text-xs">{String(item.id ?? '—')}</td><td className="p-3">{String(item.username ?? item.name ?? item.clientId ?? item.alias ?? '—')}</td><td className="p-3">{String(item.email ?? item.path ?? item.description ?? '—')}</td><td className="p-3">{typeof item.enabled === 'boolean' ? item.enabled ? 'فعال' : 'غیرفعال' : String(item.type ?? item.operationType ?? '—')}</td></tr>)}</tbody></table></div>}
            {listing.data.truncated && <p className="mt-4 text-sm text-muted-foreground">نتایج محدود شده‌اند؛ برای مشاهدهٔ موارد بیشتر، جستجو را دقیق‌تر کنید.</p>}
          </CardContent></Card>}
        </>}
      </div>
    </PageContainer>
  );
}

function Metric({ title, value }: { title: string; value: string | number }) {
  return <Card><CardHeader className="pb-2"><CardDescription>{title}</CardDescription><CardTitle className="break-all text-xl">{value}</CardTitle></CardHeader></Card>;
}