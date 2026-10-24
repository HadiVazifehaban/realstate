'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import { Icons } from '@/components/icons';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger
} from '@/components/ui/sheet';
import { toPersianDigits } from '@/lib/utils';

import { revalueProperty } from '../api/client';
import type { ValuationResponse } from '../types';

const STATUS_LABELS: Record<string, string> = {
  BARGAIN: 'زیر بازار',
  FAIR: 'منصفانه',
  OVERPRICED: 'بالای بازار',
  INSUFFICIENT_DATA: 'داده ناکافی'
};

function formatToman(value: number | null): string {
  if (value === null) return '—';
  return `${toPersianDigits(value.toLocaleString('en-US'))} تومان`;
}

/**
 * Value one specific file.
 *
 * AVM is a *server* judgement: the hedonic cohort is built from comparable
 * listings in PostGIS, so the browser only supplies a property id and renders
 * the verdict. It never computes a price locally.
 *
 * Kept as a sheet rather than a section of the market page because the two
 * answer different questions — "what is this unit worth?" versus "which
 * neighbourhoods are dear?" — and stacking them made both look like the same
 * screen.
 */
export function PropertyAvmSheet() {
  const [open, setOpen] = useState(false);
  const [propertyId, setPropertyId] = useState('');
  const [result, setResult] = useState<ValuationResponse | null>(null);

  const value = useMutation({
    mutationFn: () => revalueProperty(propertyId.trim()),
    onSuccess: setResult
  });

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger render={<Button size='sm' variant='outline' />}>
        <Icons.sparkles className='size-4' />
        ارزش‌گذاری یک ملک
      </SheetTrigger>

      <SheetContent side='left' className='sm:max-w-md'>
        <SheetHeader className='border-border border-b'>
          <SheetTitle>ارزش‌گذاری یک ملک</SheetTitle>
          <SheetDescription>
            شناسهٔ فایل را بدهید تا هم‌گروه همسایگی ساخته و قیمت ارزیابی شود.
          </SheetDescription>
        </SheetHeader>

        <div className='flex-1 space-y-4 overflow-y-auto p-4'>
          <div className='space-y-2'>
            <Label htmlFor='avm-property'>شناسهٔ ملک</Label>
            <Input
              id='avm-property'
              value={propertyId}
              onChange={(event) => setPropertyId(event.target.value)}
              placeholder='مثلاً ۸۸۹۱۲۳۴۵'
              dir='ltr'
            />
          </div>

          {value.error && (
            <Alert variant='destructive'>
              <AlertTitle>ارزش‌گذاری انجام نشد</AlertTitle>
              <AlertDescription>{(value.error as Error).message}</AlertDescription>
            </Alert>
          )}

          <Button
            onClick={() => value.mutate()}
            disabled={propertyId.trim().length === 0 || value.isPending}
          >
            {value.isPending ? 'در حال محاسبه…' : 'محاسبهٔ ارزش'}
          </Button>

          {result && (
            <div className='space-y-4'>
              <Separator />

              <div className='flex flex-wrap items-center gap-2'>
                <Badge variant={result.bargain ? 'default' : 'secondary'}>
                  {STATUS_LABELS[result.valuation_status] ?? result.valuation_status}
                </Badge>
                {result.bargain && (
                  <span className='text-muted-foreground text-xs'>
                    این ملک زیر قیمت بازار است
                  </span>
                )}
              </div>

              <div className='space-y-2'>
                <Row label='میانهٔ قیمت هر متر' value={formatToman(result.median_price_per_meter)} />
                <Row
                  label='انحراف از میانه'
                  value={
                    result.deviation_pct === null
                      ? '—'
                      : `${toPersianDigits(result.deviation_pct.toFixed(1))}٪`
                  }
                />
                <Row
                  label='تعداد نمونهٔ مقایسه‌ای'
                  value={toPersianDigits(result.sample_count.toLocaleString('en-US'))}
                />
              </div>

              {Object.keys(result.explain).length > 0 && (
                <>
                  <Separator />
                  <div>
                    <div className='text-muted-foreground mb-2 text-xs'>جزئیات محاسبه</div>
                    <pre
                      className='bg-muted overflow-x-auto rounded-lg p-3 text-xs'
                      dir='ltr'
                    >
                      {JSON.stringify(result.explain, null, 2)}
                    </pre>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className='flex items-center justify-between gap-4'>
      <span className='text-muted-foreground text-sm'>{label}</span>
      <span className='font-mono font-bold'>{value}</span>
    </div>
  );
}
