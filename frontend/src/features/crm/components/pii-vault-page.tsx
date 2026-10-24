"use client";

import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import PageContainer from '@/components/layout/page-container';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { fetchQuota, revealContact } from '@/features/crm/api/client';
import type { Actor, PiiReveal } from '@/features/crm/types';
import { MaskedPhone } from './reveal-contact-button';

/**
 * Revealing an owner phone spends quota and writes an append-only audit row, so
 * the form asks for a reason and the result is shown once — it is deliberately
 * not cached into any list.
 */
export default function PiiVaultPage() {
  const [propertyId, setPropertyId] = useState("");
  const [reason, setReason] = useState("");
  const [revealed, setRevealed] = useState<PiiReveal | null>(null);
  const [actor] = useState<Actor>({ role: "AGENT", tier: "PRO" });

  const quota = useQuery({
    queryKey: ["crm", "pii-quota", actor.role, actor.tier],
    queryFn: () => fetchQuota(actor)
  });

  const reveal = useMutation({
    mutationFn: () => revealContact(propertyId.trim(), reason.trim(), actor),
    onSuccess: (result) => {
      setRevealed(result);
      setReason("");
      void quota.refetch();
    }
  });

  const canSubmit = propertyId.trim().length > 0 && reason.trim().length > 0 && !reveal.isPending;

  return (
    <PageContainer
      pageTitle='خزانه اطلاعات هویتی'
      pageDescription='افشای شمارهٔ تماس مالک با ثبت لاگ ممیزی و کسر از سهمیه.'
    >
      <div className='grid gap-4 lg:grid-cols-3'>
        <Card>
          <CardHeader>
            <CardTitle className='text-base'>سهمیهٔ بازدید</CardTitle>
            <CardDescription>بر اساس نقش و سطح اشتراک جاری.</CardDescription>
          </CardHeader>
          <CardContent>
            {quota.isPending && <Skeleton className='h-10' />}
            {quota.error && (
              <Alert variant='destructive'>
                <AlertTitle>دریافت سهمیه ناموفق بود</AlertTitle>
                <AlertDescription>{(quota.error as Error).message}</AlertDescription>
              </Alert>
            )}
            {quota.data && (
              <div className='space-y-1'>
                <div className='text-muted-foreground text-xs'>سطح اشتراک</div>
                <div className='font-mono text-lg font-bold'>{quota.data.tier}</div>
                <div className='text-muted-foreground mt-3 text-xs'>باقی‌مانده</div>
                <div className='font-mono text-2xl font-bold'>
                  {quota.data.remaining === null
                    ? "نامحدود"
                    : new Intl.NumberFormat("fa-IR").format(quota.data.remaining)}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className='lg:col-span-2'>
          <CardHeader>
            <CardTitle className='text-base'>افشای تماس</CardTitle>
            <CardDescription>هر افشا یک رکورد ممیزی می‌نویسد. دلیل الزامی است.</CardDescription>
          </CardHeader>
          <CardContent className='space-y-4'>
            <div className='space-y-2'>
              <Label htmlFor='property-id'>شناسهٔ ملک</Label>
              <Input
                id='property-id'
                value={propertyId}
                onChange={(e) => setPropertyId(e.target.value)}
                placeholder='مثلاً ۸۸۹۱۲۳۴۵'
                dir='ltr'
              />
            </div>

            <div className='space-y-2'>
              <Label htmlFor='reason'>دلیل افشا</Label>
              <Input
                id='reason'
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder='مثلاً توافق با مالک برای بازدید'
              />
            </div>

            {reveal.error && (
              <Alert variant='destructive'>
                <AlertTitle>افشا انجام نشد</AlertTitle>
                <AlertDescription>{(reveal.error as Error).message}</AlertDescription>
              </Alert>
            )}

            <Button onClick={() => reveal.mutate()} disabled={!canSubmit}>
              {reveal.isPending ? "در حال ثبت…" : "افشای شمارهٔ تماس"}
            </Button>

            {revealed && (
              <div className='border-border bg-muted/40 space-y-2 rounded-lg border p-4'>
                <div className='text-muted-foreground text-xs'>نتیجه</div>
                <div className='flex items-center justify-between gap-4'>
                  <span className='text-sm'>نام مالک</span>
                  <span className='font-medium'>{revealed.owner_name ?? "—"}</span>
                </div>
                <div className='flex items-center justify-between gap-4'>
                  <span className='text-sm'>شمارهٔ تماس</span>
                  {/* Deliberately masked: the page is shared and stays open on a
                      desk screen, so the plaintext is only ever one click away
                      rather than sitting rendered. */}
                  <MaskedPhone
                    value={revealed.owner_phone}
                    onReveal={() => undefined}
                    className='font-mono font-bold'
                  />
                </div>
                <div className='text-muted-foreground flex items-center justify-between gap-4 text-xs'>
                  <span>سهمیهٔ باقی‌مانده</span>
                  <span className='font-mono'>
                    {revealed.remaining_quota === null
                      ? "نامحدود"
                      : new Intl.NumberFormat("fa-IR").format(revealed.remaining_quota)}
                  </span>
                </div>
                <div className='text-muted-foreground text-xs'>
                  {revealed.audit_logged
                    ? "این افشا در لاگ ممیزی ثبت شد."
                    : "توجه: ثبت در لاگ ممیزی تأیید نشد."}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  );
}
