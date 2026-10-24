'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useRequestOtp, useVerifyOtp, useOtpAuditTrail, useOtpStatus } from '../api/queries';
import { useQueryClient } from '@tanstack/react-query';
import { Icons } from '@/components/icons';

export default function OtpManagementPage() {
  const [mobile, setMobile] = useState('');
  const [code, setCode] = useState('');
  const [purpose, setPurpose] = useState<'login' | 'register'>('login');
  const queryClient = useQueryClient();

  const requestOtpMutation = useRequestOtp();
  const verifyOtpMutation = useVerifyOtp();
  const { data: auditTrail } = useOtpAuditTrail(mobile);
  const { data: status } = useOtpStatus(mobile);

  const handleRequestOtp = async () => {
    if (!mobile) return;
    try {
      await requestOtpMutation.mutateAsync({ mobile, purpose });
      queryClient.invalidateQueries({ queryKey: ['otp', 'audit', mobile] });
    } catch (error) {
      console.error('OTP request failed:', error);
    }
  };

  const handleVerifyOtp = async () => {
    if (!mobile || !code) return;
    try {
      await verifyOtpMutation.mutateAsync({ mobile, code });
      queryClient.invalidateQueries({ queryKey: ['otp', 'status', mobile] });
      queryClient.invalidateQueries({ queryKey: ['otp', 'audit', mobile] });
      setCode('');
    } catch (error) {
      console.error('OTP verification failed:', error);
    }
  };

  const formatTimestamp = (ts: number) => {
    return new Date(ts * 1000).toLocaleString('fa-IR');
  };

  const getEventIcon = (event: string) => {
    switch (event) {
      case 'request:sent':
        return <Icons.circleCheck className='h-4 w-4 text-green-500' />;
      case 'verify:ok':
        return <Icons.circleCheck className='h-4 w-4 text-green-500' />;
      case 'verify:wrong':
      case 'verify:attempts_exhausted':
        return <Icons.alertCircle className='h-4 w-4 text-red-500' />;
      default:
        return <Icons.clock className='h-4 w-4 text-gray-500' />;
    }
  };

  const getEventLabel = (event: string) => {
    const labels: Record<string, string> = {
      'request:sent': 'ارسال کد',
      'request:cooldown': 'زمان انتظار',
      'request:hour_limit': 'محدودیت ساعتی',
      'request:ip_limit': 'محدودیت IP',
      'request:sms_failed': 'خطای SMS',
      'verify:ok': 'تأیید موفق',
      'verify:wrong': 'کد اشتباه',
      'verify:expired': 'انقضا',
      'verify:attempts_exhausted': 'تلاش‌های تمام شده',
      'verify:replay': 'تکرار درخواست'
    };
    return labels[event] || event;
  };

  return (
    <div className='space-y-6'>
      <div className='grid gap-6 md:grid-cols-2'>
        {/* Request OTP Card */}
        <Card>
          <CardHeader>
            <CardTitle className='flex items-center gap-2'>
              <Icons.lock className='h-5 w-5' />
              درخواست کد OTP
            </CardTitle>
            <CardDescription>ارسال کد تأیید به شماره موبایل</CardDescription>
          </CardHeader>
          <CardContent className='space-y-4'>
            <div className='space-y-2'>
              <Label htmlFor='mobile'>شماره موبایل</Label>
              <Input
                id='mobile'
                placeholder='09123456789'
                value={mobile}
                onChange={(e) => setMobile(e.target.value)}
                dir='ltr'
              />
            </div>
            <div className='space-y-2'>
              <Label htmlFor='purpose'>هدف</Label>
              <select
                id='purpose'
                value={purpose}
                onChange={(e) => setPurpose(e.target.value as 'login' | 'register')}
                className='flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm'
              >
                <option value='login'>ورود</option>
                <option value='register'>ثبت‌نام</option>
              </select>
            </div>
            <Button
              onClick={handleRequestOtp}
              disabled={!mobile || requestOtpMutation.isPending}
              className='w-full'
            >
              {requestOtpMutation.isPending ? 'در حال ارسال...' : 'ارسال کد'}
            </Button>
            {requestOtpMutation.data?.dev_code && (
              <div className='p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-md border border-yellow-200 dark:border-yellow-800'>
                <p className='text-sm text-yellow-800 dark:text-yellow-200'>
                  کد تست: <span className='font-mono font-bold'>{requestOtpMutation.data.dev_code}</span>
                </p>
              </div>
            )}
            {requestOtpMutation.data?.retry_after !== undefined && requestOtpMutation.data.retry_after > 0 && (
              <p className='text-sm text-muted-foreground'>
                لطفاً {requestOtpMutation.data.retry_after} ثانیه صبر کنید
              </p>
            )}
          </CardContent>
        </Card>

        {/* Verify OTP Card */}
        <Card>
          <CardHeader>
            <CardTitle className='flex items-center gap-2'>
              <Icons.circleCheck className='h-5 w-5' />
              تأیید کد OTP
            </CardTitle>
            <CardDescription>بررسی کد تأیید ارسال‌شده</CardDescription>
          </CardHeader>
          <CardContent className='space-y-4'>
            <div className='space-y-2'>
              <Label htmlFor='code'>کد تأیید</Label>
              <Input
                id='code'
                placeholder='123456'
                value={code}
                onChange={(e) => setCode(e.target.value)}
                maxLength={6}
                dir='ltr'
              />
            </div>
            <Button
              onClick={handleVerifyOtp}
              disabled={!mobile || !code || verifyOtpMutation.isPending}
              className='w-full'
            >
              {verifyOtpMutation.isPending ? 'در حال بررسی...' : 'تأیید کد'}
            </Button>
            {verifyOtpMutation.data?.ok && (
              <div className='p-3 bg-green-50 dark:bg-green-900/20 rounded-md border border-green-200 dark:border-green-800'>
                <p className='text-sm text-green-800 dark:text-green-200'>
                  کد تأیید شد. توکن ثبت‌نام: {verifyOtpMutation.data.registration_token?.slice(0, 16)}...
                </p>
              </div>
            )}
            {verifyOtpMutation.data && !verifyOtpMutation.data.ok && (
              <div className='p-3 bg-red-50 dark:bg-red-900/20 rounded-md border border-red-200 dark:border-red-800'>
                <p className='text-sm text-red-800 dark:text-red-200'>
                  {verifyOtpMutation.data.reason === 'expired' && 'کد منقضی شده است'}
                  {verifyOtpMutation.data.reason === 'invalid' && 'کد اشتباه است'}
                  {verifyOtpMutation.data.reason === 'attempts_exhausted' && 'تعداد تلاش‌ها تمام شده'}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Status Card */}
      {status && (
        <Card>
          <CardHeader>
            <CardTitle>وضعیت تأیید شماره</CardTitle>
          </CardHeader>
          <CardContent>
            <div className='flex items-center gap-4'>
              {status.is_verified ? (
                <div className='flex items-center gap-2 text-green-600 dark:text-green-400'>
                  <Icons.circleCheck className='h-5 w-5' />
                  <span>شماره تأیید شده است</span>
                </div>
              ) : (
                <div className='flex items-center gap-2 text-gray-600 dark:text-gray-400'>
                  <Icons.alertCircle className='h-5 w-5' />
                  <span>شماره تأیید نشده است</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Audit Trail Card */}
      {mobile && auditTrail && auditTrail.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className='flex items-center gap-2'>
              <Icons.clock className='h-5 w-5' />
              تاریخچه عملیات OTP
            </CardTitle>
            <CardDescription>آخرین فعالیت‌های مربوط به این شماره</CardDescription>
          </CardHeader>
          <CardContent>
            <div className='space-y-2'>
              {auditTrail.map((entry, index) => (
                <div
                  key={index}
                  className='flex items-center gap-3 p-3 rounded-md bg-muted/50'
                >
                  {getEventIcon(entry.event)}
                  <div className='flex-1'>
                    <p className='text-sm font-medium'>{getEventLabel(entry.event)}</p>
                    <p className='text-xs text-muted-foreground'>{entry.mobile}</p>
                  </div>
                  <p className='text-xs text-muted-foreground'>{formatTimestamp(entry.ts)}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
