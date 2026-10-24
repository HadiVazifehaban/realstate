'use client';

import * as React from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { IconArrowRight, IconBuilding, IconPhone } from '@tabler/icons-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { useAgency, useCreateCooperation } from '@/features/network/hooks';
import { AgencyStatusBadge, ListError, ListSkeleton } from '@/features/network/components/shared';
import { useAuthContext } from '@/hooks/use-auth';

/** پروفایل یک دفتر همکار — از `/network/agencies/{id}` می‌خواند. */
export function AgencyDetailClient() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const auth = useAuthContext();

  const { data: agency, isPending, isError, refetch } = useAgency(id);
  const createCooperation = useCreateCooperation();

  const isSelf = !!agency && agency.id === auth.tenantId;

  const handleRequest = () => {
    if (!auth.tenantId || !agency) return;
    createCooperation.mutate(
      {
        requester_agency_id: auth.tenantId,
        target_agency_id: agency.id,
        scope: 'SHARE_LISTINGS',
        default_commission_pct: 50,
        expires_in_days: 30
      },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries({ queryKey: ['network', 'cooperations'] });
        }
      }
    );
  };

  if (isPending) return <ListSkeleton rows={3} />;
  if (isError) return <ListError onRetry={() => void refetch()} />;
  if (!agency) return <p className='py-12 text-center text-muted-foreground'>دفتر مورد نظر پیدا نشد.</p>;

  return (
    <div className='space-y-5'>
      <Button variant='ghost' size='sm' onClick={() => router.push('/dashboard/network/agencies')}>
        <IconArrowRight className='ml-1 h-4 w-4' />
        بازگشت به فهرست دفاتر
      </Button>

      <Card>
        <CardHeader className='pb-3'>
          <CardTitle className='flex items-center justify-between gap-2'>
            <span className='flex items-center gap-2' dir='auto'>
              <IconBuilding className='h-5 w-5 text-primary' />
              {agency.name_fa || agency.name}
            </span>
            <AgencyStatusBadge status={agency.status} />
          </CardTitle>
        </CardHeader>
        <CardContent className='space-y-4'>
          <div className='grid gap-4 sm:grid-cols-3'>
            <Field label='نام لاتین' value={agency.name} />
            <Field label='شهر' value={agency.city} />
            <Field label='منطقه' value={agency.district} />
            <Field label='شناسهٔ دفتر' value={agency.slug} mono />
            <Field label='تاریخ عضویت' value={new Date(agency.created_at).toLocaleDateString('fa-IR')} />
            <div>
              <span className='text-xs text-muted-foreground'>تماس</span>
              <p className='mt-1 flex items-center gap-1' dir='ltr'>
                <IconPhone className='h-3.5 w-3.5 text-muted-foreground' />
                <span dir='auto'>{agency.phone || '—'}</span>
              </p>
            </div>
          </div>

          {agency.description ? (
            <>
              <Separator />
              <div>
                <span className='text-xs text-muted-foreground'>دربارهٔ دفتر</span>
                <p className='mt-1 leading-7' dir='auto'>
                  {agency.description}
                </p>
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>

      {!isSelf ? (
        <div className='flex justify-end'>
          <Button onClick={handleRequest} disabled={createCooperation.isPending}>
            ارسال درخواست همکاری
          </Button>
        </div>
      ) : (
        <p className='text-center text-sm text-muted-foreground'>این دفترِ خودِ شماست.</p>
      )}
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <span className='text-xs text-muted-foreground'>{label}</span>
      <p className={`mt-1 ${mono ? 'font-mono text-xs' : ''}`} dir='auto'>
        {value || '—'}
      </p>
    </div>
  );
}
