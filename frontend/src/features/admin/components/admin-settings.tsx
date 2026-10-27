'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { toast } from 'sonner';
import { useAuthContext } from '@/hooks/use-auth';
import PageContainer from '@/components/layout/page-container';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  approveApplication, approveDirectoryUser, fetchApplications, fetchDirectoryUsers,
  fetchPendingAgencies, rejectApplication, reviewAgency
} from '../api';

const keys = {
  agencies: ['admin-settings', 'agencies'],
  applications: ['admin-settings', 'applications'],
  users: ['admin-settings', 'users']
};

function ErrorMessage({ error }: { error: Error | null }) {
  if (!error) return null;
  return <Alert variant='destructive'><AlertTitle>خطا در دریافت اطلاعات</AlertTitle><AlertDescription>{error.message}</AlertDescription></Alert>;
}

export function AdminSettings() {
  const { roles, isLoading: authLoading } = useAuthContext();
  const allowed = roles.includes('ROLE_ADMIN');
  const client = useQueryClient();
  const [reasons, setReasons] = useState<Record<string, string>>({});

  const agencies = useQuery({ queryKey: keys.agencies, queryFn: fetchPendingAgencies, enabled: !authLoading && allowed, retry: false });
  const applications = useQuery({ queryKey: keys.applications, queryFn: fetchApplications, enabled: !authLoading && allowed, retry: false });
  const users = useQuery({ queryKey: keys.users, queryFn: fetchDirectoryUsers, enabled: !authLoading && allowed, retry: false });

  const refresh = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: keys.agencies }),
      client.invalidateQueries({ queryKey: keys.applications }),
      client.invalidateQueries({ queryKey: keys.users })
    ]);
  };
  const action = useMutation({
    mutationFn: async (input: { type: 'agency'; id: string; decision: 'APPROVE' | 'REJECT'; reason: string } | { type: 'application'; id: string; decision: 'APPROVE' | 'REJECT'; reason: string } | { type: 'user'; id: string }) => {
      if (input.type === 'agency') return reviewAgency(input.id, input.decision, input.reason);
      if (input.type === 'application') return input.decision === 'APPROVE' ? approveApplication(input.id) : rejectApplication(input.id, input.reason);
      return approveDirectoryUser(input.id);
    },
    onSuccess: async () => { toast.success('تغییرات با موفقیت ثبت شد.'); await refresh(); },
    onError: (error: Error) => toast.error(error.message)
  });

  if (authLoading) return <PageContainer pageTitle='تنظیمات مدیریت'><p className='text-muted-foreground'>در حال بررسی دسترسی…</p></PageContainer>;
  if (!allowed) return <PageContainer pageTitle='تنظیمات مدیریت' access={false} accessFallback={<p>این بخش فقط برای مدیر سامانه در دسترس است.</p>}><></></PageContainer>;

  return (
    <PageContainer pageTitle='تنظیمات مدیریت' pageDescription='صف بررسی دفاتر، درخواست‌های عضویت حرفه‌ای و حساب‌های کاربران'>
      <Tabs defaultValue='agencies' dir='rtl' className='gap-5'>
        <TabsList className='h-auto w-full flex-wrap justify-start'>
          <TabsTrigger value='agencies'>دفاتر در انتظار ({agencies.data?.length ?? '…'})</TabsTrigger>
          <TabsTrigger value='applications'>درخواست‌های کاربران ({applications.data?.total ?? '…'})</TabsTrigger>
          <TabsTrigger value='users'>حساب‌های Keycloak ({users.data?.users.length ?? '…'})</TabsTrigger>
        </TabsList>

        <TabsContent value='agencies' className='space-y-4'>
          <Card><CardHeader><CardTitle>بررسی دفاتر</CardTitle><CardDescription>دفترهای ثبت‌شدهٔ در انتظار تأیید. رد دفتر نیازمند ذکر دلیل است.</CardDescription></CardHeader>
            <CardContent className='space-y-4'><ErrorMessage error={agencies.error} />
              {agencies.isLoading && <p>در حال دریافت دفاتر…</p>}
              {agencies.isSuccess && agencies.data.length === 0 && <p className='text-muted-foreground'>دفتر در انتظاری وجود ندارد.</p>}
              {agencies.data?.map((agency) => <article key={agency.id} className='space-y-3 rounded-xl border p-4'>
                <div className='flex flex-wrap items-start justify-between gap-3'><div><h3 className='font-semibold'>{agency.name_fa || agency.name}</h3><p className='text-sm text-muted-foreground'>{[agency.city, agency.district].filter(Boolean).join('، ') || 'مکان ثبت نشده'} · {agency.phone || 'تلفن ثبت نشده'}</p></div><Badge variant='secondary'>در انتظار</Badge></div>
                {agency.description && <p className='text-sm'>{agency.description}</p>}
                <Textarea aria-label={`دلیل رد ${agency.name_fa || agency.name}`} placeholder='در صورت رد، دلیل را بنویسید…' value={reasons[agency.id] ?? ''} onChange={(event) => setReasons((current) => ({ ...current, [agency.id]: event.target.value }))} />
                <div className='flex gap-2'><Button disabled={action.isPending} onClick={() => action.mutate({ type: 'agency', id: agency.id, decision: 'APPROVE', reason: '' })}>تأیید دفتر</Button><Button variant='destructive' disabled={action.isPending || !(reasons[agency.id] ?? '').trim()} onClick={() => action.mutate({ type: 'agency', id: agency.id, decision: 'REJECT', reason: reasons[agency.id].trim() })}>رد دفتر</Button></div>
              </article>)}
              <Button variant='outline' disabled={agencies.isFetching} onClick={() => void agencies.refetch()}>بروزرسانی فهرست</Button>
            </CardContent></Card>
        </TabsContent>

        <TabsContent value='applications' className='space-y-4'>
          <Card><CardHeader><CardTitle>درخواست‌های کاربران</CardTitle><CardDescription>درخواست‌های حرفه‌ای منتظر بررسی و اعطای نقش مجاز.</CardDescription></CardHeader><CardContent className='space-y-4'><ErrorMessage error={applications.error} />
            {applications.isLoading && <p>در حال دریافت درخواست‌ها…</p>}
            {applications.isSuccess && applications.data.items.length === 0 && <p className='text-muted-foreground'>درخواست بازی در صف بررسی نیست.</p>}
            {applications.data?.items.map((item) => <article key={item.id} className='space-y-3 rounded-xl border p-4'><div className='flex flex-wrap justify-between gap-2'><div><h3 className='font-semibold'>{[item.first_name, item.last_name].filter(Boolean).join(' ') || 'نام ثبت نشده'}</h3><p className='text-sm text-muted-foreground' dir='ltr'>{item.mobile} · {item.email || 'بدون ایمیل'}</p></div><Badge variant='secondary'>{item.requested_role.replace('ROLE_', '')}</Badge></div><Textarea aria-label={`یادداشت رد ${item.first_name} ${item.last_name}`} placeholder='یادداشت رد (در صورت رد)…' value={reasons[`application:${item.id}`] ?? ''} onChange={(event) => setReasons((current) => ({ ...current, [`application:${item.id}`]: event.target.value }))} /><div className='flex gap-2'><Button disabled={action.isPending} onClick={() => action.mutate({ type: 'application', id: item.id, decision: 'APPROVE', reason: '' })}>تأیید و اعطای نقش</Button><Button variant='destructive' disabled={action.isPending} onClick={() => action.mutate({ type: 'application', id: item.id, decision: 'REJECT', reason: reasons[`application:${item.id}`] ?? '' })}>رد درخواست</Button></div></article>)}
            <Button variant='outline' disabled={applications.isFetching} onClick={() => void applications.refetch()}>بروزرسانی درخواست‌ها</Button>
          </CardContent></Card>
        </TabsContent>

        <TabsContent value='users' className='space-y-4'>
          <Card><CardHeader><CardTitle>حساب‌های Keycloak</CardTitle><CardDescription>فهرست حساب‌ها و تأیید پایه؛ تأییدهای حرفه‌ای را از زبانهٔ درخواست‌ها انجام دهید.</CardDescription></CardHeader><CardContent className='space-y-4'><ErrorMessage error={users.error} />
            {users.isLoading && <p>در حال دریافت کاربران…</p>}
            {users.data?.users.map((user) => { const approved = user.realmRoles?.includes('ROLE_OWNER'); return <article key={user.id} className='flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4'><div><h3 className='font-semibold'>{[user.firstName, user.lastName].filter(Boolean).join(' ') || user.username}</h3><p className='text-sm text-muted-foreground' dir='ltr'>{user.email || user.username}</p><div className='mt-2 flex flex-wrap gap-1'>{user.realmRoles?.map((role) => <Badge key={role} variant='outline'>{role}</Badge>)}</div></div><div className='flex items-center gap-2'><Badge variant={approved ? 'default' : 'secondary'}>{approved ? 'تأییدشده' : 'تأییدنشده'}</Badge>{!approved && <Button size='sm' disabled={action.isPending || !user.enabled} onClick={() => action.mutate({ type: 'user', id: user.id })}>تأیید حساب</Button>}</div></article>; })}
            <Button variant='outline' disabled={users.isFetching} onClick={() => void users.refetch()}>بروزرسانی کاربران</Button>
          </CardContent></Card>
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}