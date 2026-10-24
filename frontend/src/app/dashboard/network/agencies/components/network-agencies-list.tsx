'use client';

import * as React from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { IconBuilding, IconPlus, IconSearch } from '@tabler/icons-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import { useDebounce } from '@/hooks/use-debounce';
import { useAgencies, useCreateCooperation } from '@/features/network/hooks';
import {
  AgencyStatusBadge,
  ListEmpty,
  ListError,
  ListSkeleton
} from '@/features/network/components/shared';
import type { Agency } from '@/features/network/types';
import { OsmCityFilter } from '@/components/OsmCityFilter';

const STATUS_FILTERS = [
  { value: 'ALL', label: 'همهٔ دفاتر' },
  { value: 'VERIFIED', label: 'تأییدشده' },
  { value: 'PENDING', label: 'در انتظار تأیید' },
  { value: 'SUSPENDED', label: 'معلق' }
] as const;

/**
 * فهرست دفاتر همکار — مستقیم از API واقعی `/network/agencies`.
 *
 * دفترِ خودِ کاربر در کارت نشان داده می‌شود اما «درخواست همکاری» برایش غیرفعال
 * است، چون دفتر نمی‌تواند با خودش همکاری کند.
 */
export function NetworkAgenciesList({
  currentAgencyId
}: {
  /** شناسهٔ دفترِ جاری کاربر — برای غیرفعال‌کردن درخواست روی کارت خودی. */
  currentAgencyId?: string | null;
}) {
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const [query, setQuery] = React.useState(searchParams.get('q') ?? '');
  const [status, setStatus] = React.useState(searchParams.get('status') ?? 'ALL');
  const [city, setCity] = React.useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('selected_city') ?? '';
    }
    return '';
  });
  const debouncedQuery = useDebounce(query, 350);

  const { data: agencies, isPending, isError, refetch } = useAgencies({
    q: debouncedQuery || undefined,
    status: status === 'ALL' ? undefined : status,
    city: city || undefined
  });

  const createCooperation = useCreateCooperation();

  const handleRequestCooperation = (targetAgencyId: string) => {
    if (!currentAgencyId) return;
    createCooperation.mutate(
      {
        requester_agency_id: currentAgencyId,
        target_agency_id: targetAgencyId,
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

  const handleCityChange = (newCity: string | undefined) => {
    const cityValue = newCity ?? '';
    setCity(cityValue);
    if (cityValue) {
      localStorage.setItem('selected_city', cityValue);
    } else {
      localStorage.removeItem('selected_city');
    }
  };

  return (
    <div className='space-y-5'>
      <div className='flex flex-col gap-3 sm:flex-row sm:items-center'>
        <div className='relative flex-1'>
          <IconSearch className='absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground' />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder='جستجو بر اساس نام دفتر، شهر یا منطقه…'
            className='pr-9'
            aria-label='جستجوی دفتر همکار'
          />
        </div>
        <div className='w-full sm:w-64'>
          <OsmCityFilter value={city || undefined} onChange={(c) => handleCityChange(c)} className='w-full' />
        </div>
        <Select value={status} onValueChange={(value) => setStatus(value ?? 'ALL')}>
          <SelectTrigger className='w-full sm:w-48' aria-label='فیلتر وضعیت'>
            <SelectValue placeholder='وضعیت' />
          </SelectTrigger>
          <SelectContent>
            {STATUS_FILTERS.map((f) => (
              <SelectItem key={f.value} value={f.value}>
                {f.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isPending ? <ListSkeleton rows={6} /> : null}
      {isError ? <ListError onRetry={() => void refetch()} /> : null}

      {!isPending && !isError && (agencies?.length ?? 0) === 0 ? (
        <ListEmpty
          title='دفتری پیدا نشد'
          description='با تغییر عبارت جستجو یا فیلتر وضعیت یا شهر، دفاتر بیشتری را ببینید.'
        />
      ) : null}

      {!isPending && !isError && (agencies?.length ?? 0) > 0 ? (
        <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
          {agencies!.map((agency) => (
            <AgencyCard
              key={agency.id}
              agency={agency}
              isSelf={agency.id === currentAgencyId}
              onRequest={() => handleRequestCooperation(agency.id)}
              pending={createCooperation.isPending}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function AgencyCard({
  agency,
  isSelf,
  onRequest,
  pending
}: {
  agency: Agency;
  isSelf: boolean;
  onRequest: () => void;
  pending: boolean;
}) {
  const router = useRouter();
  return (
    <Card className='flex flex-col border border-border bg-card transition-colors hover:border-primary/40'>
      <CardHeader className='pb-3'>
        <CardTitle className='flex items-center justify-between gap-2 text-base'>
          <span className='flex items-center gap-2 truncate'>
            <IconBuilding className='h-4 w-4 shrink-0 text-primary' />
            <span className='truncate' dir='auto'>
              {agency.name_fa || agency.name}
            </span>
          </span>
          <AgencyStatusBadge status={agency.status} />
        </CardTitle>
      </CardHeader>
      <CardContent className='flex flex-1 flex-col gap-3 text-sm'>
        <p className='text-muted-foreground' dir='auto'>
          {agency.city}، {agency.district}
        </p>
        {agency.description ? (
          <p className='line-clamp-2 text-muted-foreground' dir='auto'>
            {agency.description}
          </p>
        ) : null}
        <div className='mt-auto flex gap-2 pt-2'>
          <Button
            size='sm'
            variant='outline'
            className='flex-1'
            onClick={() => router.push(`/dashboard/network/agencies/${agency.id}`)}
          >
            مشاهده پروفایل
          </Button>
          {isSelf ? (
            <span className='flex flex-1 items-center justify-center rounded-md bg-muted px-3 text-xs text-muted-foreground'>
              دفتر شما
            </span>
          ) : (
            <Button size='sm' className='flex-1' disabled={pending} onClick={onRequest}>
              <IconPlus className='ml-1 h-3.5 w-3.5' />
              درخواست همکاری
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
