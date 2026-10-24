"use client";

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import PageContainer from '@/components/layout/page-container';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
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
import { CrmApiError, fetchPiiAudit } from '@/features/crm/api/client';
import type { Actor } from '@/features/crm/types';

const LIMITS = [25, 50, 100, 250];

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return new Intl.DateTimeFormat("fa-IR", {
    dateStyle: "short",
    timeStyle: "medium"
  }).format(parsed);
}

/**
 * The server restricts this trail to SUPERVISOR/ADMIN and answers 403 for any
 * other role. That refusal is surfaced verbatim — an empty table must never be
 * mistaken for "no one has accessed PII".
 */
export default function PiiAuditPage() {
  const [limit, setLimit] = useState(100);
  const [actor] = useState<Actor>({ role: "ADMIN", tier: "ENTERPRISE" });

  const audit = useQuery({
    queryKey: ["crm", "pii-audit", limit],
    queryFn: () => fetchPiiAudit(limit, actor)
  });

  const forbidden = audit.error instanceof CrmApiError && audit.error.status === 403;

  return (
    <PageContainer
      pageTitle='لاگ ممیزی اطلاعات هویتی'
      pageDescription='سیاههٔ فقط‌افزودنیِ دسترسی به شمارهٔ مالکان. مشاهده تنها برای ناظر و مدیر ارشد.'
    >
      <Card>
        <CardHeader>
          <div className='flex flex-wrap items-center justify-between gap-3'>
            <div>
              <CardTitle className='text-base'>دسترسی‌ها</CardTitle>
              <CardDescription>
                {audit.data
                  ? `${new Intl.NumberFormat("fa-IR").format(audit.data.length)} رکورد`
                  : "در حال دریافت…"}
              </CardDescription>
            </div>
            <div className='flex gap-2'>
              {LIMITS.map((option) => (
                <Button
                  key={option}
                  size='sm'
                  variant={limit === option ? "default" : "outline"}
                  onClick={() => setLimit(option)}
                >
                  {new Intl.NumberFormat("fa-IR").format(option)}
                </Button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {audit.isPending && <Skeleton className='h-64' />}

          {forbidden && (
            <Alert variant='destructive'>
              <AlertTitle>دسترسی مجاز نیست</AlertTitle>
              <AlertDescription>{(audit.error as Error).message}</AlertDescription>
            </Alert>
          )}

          {audit.error && !forbidden && (
            <Alert variant='destructive'>
              <AlertTitle>دریافت لاگ ممیزی ناموفق بود</AlertTitle>
              <AlertDescription>{(audit.error as Error).message}</AlertDescription>
            </Alert>
          )}

          {audit.data && audit.data.length === 0 && (
            <p className='text-muted-foreground py-8 text-center text-sm'>
              رکوردی برای نمایش وجود ندارد.
            </p>
          )}

          {audit.data && audit.data.length > 0 && (
            <div className='overflow-x-auto'>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>کاربر</TableHead>
                    <TableHead>ملک</TableHead>
                    <TableHead>اقدام</TableHead>
                    <TableHead>نتیجه</TableHead>
                    <TableHead>دلیل</TableHead>
                    <TableHead>IP</TableHead>
                    <TableHead>زمان</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {audit.data.map((entry) => (
                    <TableRow key={entry.id}>
                      <TableCell className='font-mono text-xs'>
                        {entry.user_id?.slice(0, 8) ?? "—"}
                      </TableCell>
                      <TableCell className='font-mono text-xs'>
                        {entry.property_id?.slice(0, 8) ?? "—"}
                      </TableCell>
                      <TableCell className='text-xs'>{entry.action}</TableCell>
                      <TableCell>
                        <Badge variant={entry.allowed ? "secondary" : "destructive"}>
                          {entry.allowed ? "مجاز" : "رد شد"}
                        </Badge>
                      </TableCell>
                      <TableCell className='max-w-48 truncate text-xs'>
                        {entry.reason || "—"}
                      </TableCell>
                      <TableCell className='font-mono text-xs' dir='ltr'>
                        {entry.client_ip}
                      </TableCell>
                      <TableCell className='text-xs'>{formatTimestamp(entry.created_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </PageContainer>
  );
}
